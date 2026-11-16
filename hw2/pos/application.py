"""Сценарии ПОС и порты для внешнего хранения и экспорта."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pos.domain import Course, FullRubric, GradedOnly, ResultCalculator, Student


class CourseRepository(Protocol):
    def load(self) -> Course: ...
    def save(self, course: Course) -> None: ...


class ResultsExporter(Protocol):
    def export(self, path: Path, rows: list["Result"]) -> None: ...


@dataclass(frozen=True)
class Result:
    student: Student
    total: Decimal
    current: Decimal
    graded_count: int
    criteria_count: int


class PosFacade:
    """Facade: консоль обращается только сюда, не работает с JSON и CSV."""
    def __init__(self, repository: CourseRepository, exporter: ResultsExporter) -> None:
        self._repository = repository
        self._exporter = exporter
        self._course = repository.load()
        self._full = ResultCalculator(FullRubric())
        self._current = ResultCalculator(GradedOnly())

    @property
    def students(self):
        return self._course.students

    @property
    def criteria(self):
        return self._course.criteria

    def add_student(self, name: str):
        result = self._course.add_student(name)
        self._repository.save(self._course)
        return result

    def rename_student(self, student_id: int, name: str):
        result = self._course.rename_student(student_id, name)
        self._repository.save(self._course)
        return result

    def remove_student(self, student_id: int) -> None:
        self._course.remove_student(student_id)
        self._repository.save(self._course)

    def add_criterion(self, name: str, maximum: object, weight: object):
        result = self._course.add_criterion(name, maximum, weight)
        self._repository.save(self._course)
        return result

    def update_criterion(self, criterion_id: int, name: str,
                         maximum: object, weight: object):
        result = self._course.update_criterion(criterion_id, name, maximum, weight)
        self._repository.save(self._course)
        return result

    def remove_criterion(self, criterion_id: int) -> None:
        self._course.remove_criterion(criterion_id)
        self._repository.save(self._course)

    def set_grade(self, student_id: int, criterion_id: int,
                  score: object, comment: str = ""):
        result = self._course.set_grade(student_id, criterion_id, score, comment)
        self._repository.save(self._course)
        return result

    def grades_for(self, student_id: int):
        grades = {g.criterion_id: g for g in self._course.grades_for(student_id)}
        return [(c, grades.get(c.id)) for c in self._course.criteria]

    def remove_grade(self, student_id: int, criterion_id: int) -> None:
        self._course.remove_grade(student_id, criterion_id)
        self._repository.save(self._course)

    def result_for(self, student_id: int) -> Result:
        student = self._course.student(student_id)
        return Result(student, self._full.calculate(self._course, student_id),
                      self._current.calculate(self._course, student_id),
                      len(self._course.grades_for(student_id)),
                      len(self._course.criteria))

    def results(self) -> list[Result]:
        return [self.result_for(s.id) for s in self._course.students]

    def export_results(self, path: Path) -> None:
        self._exporter.export(path, self.results())
