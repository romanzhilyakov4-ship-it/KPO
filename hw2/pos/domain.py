"""Предметная область ПОС: студенты, критерии, оценки и итог."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol


def number(value: object) -> Decimal:
    """Число для балла или веса. Запятая в строке тоже допустима."""
    if isinstance(value, bool):
        raise ValueError("Введите число")
    try:
        result = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Введите число") from None
    if not result.is_finite():
        raise ValueError("Число должно быть конечным")
    return result


def check_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Название не может быть пустым")


def check_id(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("ID должен быть положительным целым числом")


@dataclass(frozen=True)
class Student:
    id: int
    name: str

    def __post_init__(self) -> None:
        check_id(self.id)
        check_name(self.name)


@dataclass(frozen=True)
class Criterion:
    id: int
    name: str
    max_score: Decimal
    weight: Decimal

    def __post_init__(self) -> None:
        check_id(self.id)
        check_name(self.name)
        maximum, weight = number(self.max_score), number(self.weight)
        if maximum <= 0 or weight <= 0:
            raise ValueError("Максимум и вес должны быть больше нуля")
        object.__setattr__(self, "max_score", maximum)
        object.__setattr__(self, "weight", weight)


@dataclass(frozen=True)
class Score:
    """Value Object: балл не может быть отрицательным."""
    value: Decimal

    def __post_init__(self) -> None:
        value = number(self.value)
        if value < 0:
            raise ValueError("Балл не может быть отрицательным")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class Evaluation:
    student_id: int
    criterion_id: int
    score: Score
    comment: str = ""

    def __post_init__(self) -> None:
        check_id(self.student_id)
        check_id(self.criterion_id)
        if not isinstance(self.score, Score):
            raise ValueError("Балл должен быть объектом Score")
        if not isinstance(self.comment, str):
            raise ValueError("Комментарий должен быть строкой")


class EvaluationFactory:
    """Factory: одна проверка при создании и исправлении оценки."""
    @staticmethod
    def create(student: Student, criterion: Criterion, score: object,
               comment: str = "") -> Evaluation:
        value = Score(score)
        if value.value > criterion.max_score:
            raise ValueError(f"Максимальный балл по критерию: {criterion.max_score}")
        if not isinstance(comment, str):
            raise ValueError("Комментарий должен быть строкой")
        return Evaluation(student.id, criterion.id, value, comment)


class Course:
    """Агрегат: все изменения оценок проходят через рубрикатор курса."""
    def __init__(self) -> None:
        self._students: dict[int, Student] = {}
        self._criteria: dict[int, Criterion] = {}
        self._grades: dict[tuple[int, int], Evaluation] = {}
        self._next_student_id = 1
        self._next_criterion_id = 1

    @property
    def next_student_id(self) -> int:
        return self._next_student_id

    @property
    def next_criterion_id(self) -> int:
        return self._next_criterion_id

    @property
    def students(self) -> tuple[Student, ...]:
        return tuple(self._students[key] for key in sorted(self._students))

    @property
    def criteria(self) -> tuple[Criterion, ...]:
        return tuple(self._criteria[key] for key in sorted(self._criteria))

    @property
    def grades(self) -> tuple[Evaluation, ...]:
        return tuple(self._grades[key] for key in sorted(self._grades))

    def student(self, student_id: int) -> Student:
        check_id(student_id)
        if student_id not in self._students:
            raise ValueError("Студент не найден")
        return self._students[student_id]

    def criterion(self, criterion_id: int) -> Criterion:
        check_id(criterion_id)
        if criterion_id not in self._criteria:
            raise ValueError("Критерий не найден")
        return self._criteria[criterion_id]

    def add_student(self, name: str) -> Student:
        student = Student(self.next_student_id, name.strip() if isinstance(name, str) else name)
        self._students[student.id] = student
        self._next_student_id += 1
        return student

    def rename_student(self, student_id: int, name: str) -> Student:
        self.student(student_id)
        student = Student(student_id, name.strip() if isinstance(name, str) else name)
        self._students[student_id] = student
        return student

    def remove_student(self, student_id: int) -> None:
        self.student(student_id)
        del self._students[student_id]
        self._grades = {key: grade for key, grade in self._grades.items()
                        if key[0] != student_id}

    def add_criterion(self, name: str, maximum: object, weight: object) -> Criterion:
        criterion = Criterion(self.next_criterion_id, name.strip() if isinstance(name, str) else name,
                              maximum, weight)
        self._criteria[criterion.id] = criterion
        self._next_criterion_id += 1
        return criterion

    def update_criterion(self, criterion_id: int, name: str,
                         maximum: object, weight: object) -> Criterion:
        self.criterion(criterion_id)
        new = Criterion(criterion_id, name.strip() if isinstance(name, str) else name,
                        maximum, weight)
        if any(grade.criterion_id == criterion_id and grade.score.value > new.max_score
               for grade in self._grades.values()):
            raise ValueError("Новый максимум меньше уже выставленной оценки")
        self._criteria[criterion_id] = new
        return new

    def remove_criterion(self, criterion_id: int) -> None:
        self.criterion(criterion_id)
        del self._criteria[criterion_id]
        self._grades = {key: grade for key, grade in self._grades.items()
                        if key[1] != criterion_id}

    def set_grade(self, student_id: int, criterion_id: int, score: object,
                  comment: str = "") -> Evaluation:
        grade = EvaluationFactory.create(self.student(student_id),
                                         self.criterion(criterion_id), score, comment)
        self._grades[(student_id, criterion_id)] = grade
        return grade

    def grades_for(self, student_id: int) -> tuple[Evaluation, ...]:
        self.student(student_id)
        return tuple(grade for grade in self.grades if grade.student_id == student_id)

    def remove_grade(self, student_id: int, criterion_id: int) -> None:
        self.student(student_id)
        self.criterion(criterion_id)
        if (student_id, criterion_id) not in self._grades:
            raise ValueError("Оценка не найдена")
        del self._grades[(student_id, criterion_id)]

    @classmethod
    def restore(cls, students: list[Student], criteria: list[Criterion],
                grades: list[Evaluation], next_student_id: int,
                next_criterion_id: int) -> "Course":
        """При загрузке ещё раз проверяем связи и все ограничения."""
        course = cls()
        for student in students:
            if student.id in course._students:
                raise ValueError("Повторяющийся ID студента")
            course._students[student.id] = student
        for criterion in criteria:
            if criterion.id in course._criteria:
                raise ValueError("Повторяющийся ID критерия")
            course._criteria[criterion.id] = criterion
        check_id(next_student_id)
        check_id(next_criterion_id)
        if (next_student_id <= max(course._students, default=0)
                or next_criterion_id <= max(course._criteria, default=0)):
            raise ValueError("Неверные счётчики ID")
        course._next_student_id, course._next_criterion_id = next_student_id, next_criterion_id
        for grade in grades:
            key = (grade.student_id, grade.criterion_id)
            if key in course._grades:
                raise ValueError("Повторяющаяся оценка")
            course.set_grade(*key, grade.score.value, grade.comment)
        return course


class ScoringRule(Protocol):
    def select(self, criteria: tuple[Criterion, ...],
               graded: set[int]) -> tuple[Criterion, ...]: ...


class FullRubric:
    """Итог за весь курс: отсутствие оценки считается нулём."""
    def select(self, criteria: tuple[Criterion, ...],
               graded: set[int]) -> tuple[Criterion, ...]:
        return criteria


class GradedOnly:
    """Промежуточный итог: только уже оценённые критерии."""
    def select(self, criteria: tuple[Criterion, ...],
               graded: set[int]) -> tuple[Criterion, ...]:
        return tuple(c for c in criteria if c.id in graded)


class ResultCalculator:
    """Domain Service + Strategy: итог не хранится, а рассчитывается."""
    def __init__(self, rule: ScoringRule) -> None:
        self.rule = rule

    def calculate(self, course: Course, student_id: int) -> Decimal:
        grades = {g.criterion_id: g.score.value for g in course.grades_for(student_id)}
        criteria = self.rule.select(course.criteria, set(grades))
        total_weight = sum((c.weight for c in criteria), Decimal(0))
        if not total_weight:
            return Decimal(0)
        total = sum((grades.get(c.id, Decimal(0)) / c.max_score * c.weight
                     for c in criteria), Decimal(0))
        return total / total_weight * 100
