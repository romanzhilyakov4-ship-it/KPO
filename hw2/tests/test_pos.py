"""Проверки предметных правил, хранения, экспорта и консольных сценариев."""

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from main import Container, run
from pos.adapters import CsvResultsExporter, JsonCourseRepository
from pos.application import PosFacade
from pos.domain import (Course, Criterion, Evaluation, FullRubric,
                        GradedOnly, ResultCalculator, Score, Student)


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.course = Course()
        self.student = self.course.add_student("Иван")
        self.criterion = self.course.add_criterion("Работа", 10, 2)

    def test_entities_have_ids(self):
        self.assertEqual(self.student.id, 1)
        self.assertEqual(self.criterion.id, 1)
        self.assertEqual(self.course.rename_student(1, "Пётр").id, 1)

    def test_empty_names_are_forbidden(self):
        with self.assertRaises(ValueError):
            self.course.add_student("   ")
        with self.assertRaises(ValueError):
            self.course.add_criterion("", 10, 1)
        with self.assertRaises(ValueError):
            self.course.rename_student(1, " ")

    def test_criterion_parameters(self):
        for maximum, weight in [(0, 1), (1, 0), (-2, 1), (10, -1),
                                ("nan", 1), (10, "inf")]:
            with self.subTest(maximum=maximum, weight=weight):
                with self.assertRaises(ValueError):
                    self.course.add_criterion("Плохой", maximum, weight)

    def test_score_bounds(self):
        for score in [-1, 10.01, "nan", "inf", "text", True]:
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    self.course.set_grade(1, 1, score)
        self.assertEqual(self.course.set_grade(1, 1, "10").score, Score(10))
        self.assertEqual(self.course.set_grade(1, 1, 0).score, Score(0))

    def test_unknown_student_or_criterion(self):
        with self.assertRaises(ValueError):
            self.course.set_grade(2, 1, 5)
        with self.assertRaises(ValueError):
            self.course.set_grade(1, 2, 5)
        self.assertEqual(self.course.grades, ())

    def test_grade_can_be_updated_and_removed(self):
        self.course.set_grade(1, 1, 5)
        self.course.set_grade(1, 1, 7, "исправлено")
        self.assertEqual(len(self.course.grades), 1)
        self.assertEqual(self.course.grades[0].score.value, Decimal(7))
        self.assertEqual(self.course.grades[0].comment, "исправлено")
        self.course.remove_grade(1, 1)
        self.assertEqual(self.course.grades, ())
        with self.assertRaises(ValueError):
            self.course.remove_grade(1, 1)

    def test_update_criterion_protects_existing_grades(self):
        self.course.set_grade(1, 1, 8)
        with self.assertRaises(ValueError):
            self.course.update_criterion(1, "Работа", 7, 3)
        self.assertEqual(self.course.criteria[0].max_score, 10)
        self.course.update_criterion(1, "Контрольная", 8, 3)
        self.assertEqual(self.course.criteria[0].name, "Контрольная")

    def test_deletions_remove_linked_grades(self):
        self.course.set_grade(1, 1, 4)
        self.course.remove_student(1)
        self.assertEqual(self.course.grades, ())
        second = self.course.add_student("Пётр")
        self.assertEqual(second.id, 2)
        self.course.set_grade(2, 1, 8)
        self.course.remove_criterion(1)
        self.assertEqual(self.course.grades, ())

    def test_weighted_results_and_strategies(self):
        self.course.add_criterion("Проект", 20, 3)
        self.course.set_grade(1, 1, 5)
        full = ResultCalculator(FullRubric())
        graded = ResultCalculator(GradedOnly())
        self.assertEqual(full.calculate(self.course, 1), Decimal(20))
        self.assertEqual(graded.calculate(self.course, 1), Decimal(50))
        self.course.set_grade(1, 2, 20)
        self.assertEqual(full.calculate(self.course, 1), Decimal(80))

    def test_no_criteria_and_no_grades(self):
        other = Course()
        other.add_student("Иван")
        for rule in (FullRubric(), GradedOnly()):
            self.assertEqual(ResultCalculator(rule).calculate(other, 1), 0)
            self.assertEqual(ResultCalculator(rule).calculate(self.course, 1), 0)

    def test_validation_when_restoring(self):
        with self.assertRaises(ValueError):
            Course.restore([Student(1, "A")], [Criterion(1, "K", 10, 1)],
                           [Evaluation(1, 2, Score(5))], 2, 2)
        with self.assertRaises(ValueError):
            Course.restore([Student(1, "A"), Student(1, "B")], [], [], 2, 1)
        with self.assertRaises(ValueError):
            Course.restore([Student(1, "A")], [], [], 1, 1)
        with self.assertRaises(ValueError):
            Course.restore([Student(1, "A")], [Criterion(1, "K", 10, 1)],
                           [Evaluation(1, 1, Score(2)), Evaluation(1, 1, Score(3))], 2, 2)

    def test_value_object_is_immutable(self):
        score = Score("2,5")
        self.assertEqual(score.value, Decimal("2.5"))
        with self.assertRaises(AttributeError):
            score.value = Decimal(3)


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_path = Path(self.temp.name) / "data.json"
        self.app = Container(self.data_path).get_app()

    def test_full_scenario_and_persistence(self):
        self.app.add_student("Иван")
        self.app.add_student("Мария")
        self.app.add_criterion("Семинары", 10, 3)
        self.app.add_criterion("Проект", 20, 1)
        self.app.set_grade(1, 1, "8", "хорошо")
        self.app.set_grade(1, 2, "16")
        self.assertEqual(self.app.result_for(1).total, Decimal(80))
        self.assertEqual(self.app.result_for(2).total, Decimal(0))
        self.assertEqual(self.app.result_for(1).graded_count, 2)
        self.assertEqual(self.app.grades_for(1)[0][1].comment, "хорошо")
        self.assertEqual(Container(self.data_path).get_app().result_for(1).total, 80)

    def test_export_csv(self):
        self.app.add_student("Иван")
        self.app.add_criterion("Критерий", 10, 1)
        self.app.set_grade(1, 1, 7.5)
        csv_path = Path(self.temp.name) / "exports" / "result.csv"
        self.app.export_results(csv_path)
        with csv_path.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file, delimiter=";"))
        self.assertEqual(rows[1][:4], ["1", "Иван", "75.00", "75.00"])

    def test_corrupted_data_does_not_load(self):
        self.data_path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            Container(self.data_path).get_app()
        self.data_path.write_text(json.dumps({
            "next_student_id": 2, "next_criterion_id": 2,
            "students": [{"id": 1, "name": "Иван"}],
            "criteria": [{"id": 1, "name": "K", "max_score": "10", "weight": "1"}],
            "grades": [{"student_id": 1, "criterion_id": 1, "score": "11"}]
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            Container(self.data_path).get_app()

    def test_errors_do_not_save_invalid_grade(self):
        self.app.add_student("Иван")
        self.app.add_criterion("Критерий", 10, 1)
        original = self.data_path.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            self.app.set_grade(1, 1, 11)
        self.assertEqual(self.data_path.read_text(encoding="utf-8"), original)

    def test_editing_and_deletion_via_facade(self):
        self.app.add_student("Иван")
        self.app.rename_student(1, "Мария")
        self.app.add_criterion("Критерий", 10, 1)
        self.app.update_criterion(1, "Новый", 20, 2)
        self.app.set_grade(1, 1, 15)
        self.app.remove_grade(1, 1)
        self.app.remove_criterion(1)
        self.app.remove_student(1)
        self.assertEqual(self.app.students, ())
        self.assertEqual(self.app.criteria, ())

    def test_di_allows_replacing_repository(self):
        class MemoryRepo:
            def __init__(self):
                self.course = Course()
                self.saves = 0

            def load(self):
                return self.course

            def save(self, course):
                self.saves += 1
                self.course = course

        class MemoryExport:
            def export(self, path, rows):
                self.rows = rows

        repo, exporter = MemoryRepo(), MemoryExport()
        app = Container(repository=repo, exporter=exporter).get_app()
        app.add_student("Иван")
        app.export_results(Path("unused.csv"))
        self.assertEqual(repo.saves, 1)
        self.assertEqual(exporter.rows[0].student.name, "Иван")

    def test_console_end_to_end(self):
        csv_path = Path(self.temp.name) / "out.csv"
        answers = ["1", "Иван", "5", "Семинары", "10", "2", "9",
                   "1", "1", "8", "хорошо", "10", "1", "12", "1",
                   "14", str(csv_path), "0"]
        output = io.StringIO()
        with patch("builtins.input", side_effect=answers), redirect_stdout(output):
            run(self.app)
        self.assertIn("итог 80.00%", output.getvalue())
        self.assertTrue(csv_path.exists())
        self.assertIn("80.00", csv_path.read_text(encoding="utf-8-sig"))

    def test_console_invalid_input_does_not_crash(self):
        output = io.StringIO()
        with patch("builtins.input", side_effect=["5", "Работа", "0", "1", "zzz", "0"]), redirect_stdout(output):
            run(self.app)
        self.assertIn("Ошибка", output.getvalue())
        self.assertIn("Неизвестная команда", output.getvalue())


if __name__ == "__main__":
    unittest.main()
