"""Adapters: JSON-файл для хранения, CSV-файл для ведомости."""

import csv
import json
from pathlib import Path

from pos.application import Result
from pos.domain import Course, Criterion, Evaluation, Score, Student


class JsonCourseRepository:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> Course:
        if not self.path.exists():
            return Course()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            students = [Student(x["id"], x["name"]) for x in data["students"]]
            criteria = [Criterion(x["id"], x["name"], x["max_score"], x["weight"])
                        for x in data["criteria"]]
            grades = [Evaluation(x["student_id"], x["criterion_id"],
                                 Score(x["score"]), x.get("comment", ""))
                      for x in data["grades"]]
            return Course.restore(students, criteria, grades,
                                  data["next_student_id"], data["next_criterion_id"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ValueError(f"Не удалось прочитать данные: {error}") from error

    def save(self, course: Course) -> None:
        data = {
            "next_student_id": course.next_student_id,
            "next_criterion_id": course.next_criterion_id,
            "students": [vars(s) for s in course.students],
            "criteria": [{"id": c.id, "name": c.name,
                          "max_score": str(c.max_score), "weight": str(c.weight)}
                         for c in course.criteria],
            "grades": [{"student_id": g.student_id, "criterion_id": g.criterion_id,
                        "score": str(g.score.value), "comment": g.comment}
                       for g in course.grades],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")


class CsvResultsExporter:
    def export(self, path: Path, rows: list[Result]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["ID", "Студент", "Итог (%)", "По выставленным (%)",
                             "Выставлено оценок", "Всего критериев"])
            for row in rows:
                writer.writerow([row.student.id, row.student.name,
                                 f"{row.total:.2f}", f"{row.current:.2f}",
                                 row.graded_count, row.criteria_count])
