"""Консольное приложение ПОС. Запуск: python main.py"""

from pathlib import Path

from pos.adapters import CsvResultsExporter, JsonCourseRepository
from pos.application import PosFacade


class Container:
    """DI-контейнер: подбирает реализации хранилища и экспорта."""
    def __init__(self, data_file: Path | None = None,
                 repository=None, exporter=None) -> None:
        self.repository = (repository if repository is not None else
                           JsonCourseRepository(data_file or Path(__file__).with_name("data.json")))
        self.exporter = exporter if exporter is not None else CsvResultsExporter()

    def get_app(self) -> PosFacade:
        return PosFacade(self.repository, self.exporter)


def read_id(what: str) -> int:
    try:
        return int(input(f"ID {what}: "))
    except ValueError:
        raise ValueError("ID должен быть целым числом") from None


def show_result(row) -> None:
    print(f"[{row.student.id}] {row.student.name}: итог {row.total:.2f}% "
          f"(по выставленным {row.current:.2f}%), "
          f"оценок {row.graded_count}/{row.criteria_count}")


def run(app: PosFacade) -> None:
    while True:
        print("""
ПОС — преподавательская оценка студентов
 1. Добавить студента       2. Список студентов
 3. Переименовать студента  4. Удалить студента
 5. Добавить критерий       6. Список критериев
 7. Изменить критерий       8. Удалить критерий
 9. Поставить / исправить оценку
10. Посмотреть оценки      11. Удалить оценку
12. Итог студента          13. Итоги всех студентов
14. Экспорт итогов в CSV    0. Выход""")
        try:
            cmd = input("Выберите действие: ").strip()
            if cmd == "0":
                return
            elif cmd == "1":
                student = app.add_student(input("Имя студента: "))
                print(f"Добавлен студент [{student.id}] {student.name}")
            elif cmd == "2":
                for student in app.students:
                    print(f"[{student.id}] {student.name}")
                if not app.students:
                    print("Студентов пока нет")
            elif cmd == "3":
                student = app.rename_student(read_id("студента"), input("Новое имя: "))
                print(f"Студент [{student.id}] обновлён")
            elif cmd == "4":
                app.remove_student(read_id("студента"))
                print("Студент удалён вместе с оценками")
            elif cmd == "5":
                criterion = app.add_criterion(input("Название критерия: "),
                                               input("Максимальный балл: "),
                                               input("Вес: "))
                print(f"Добавлен критерий [{criterion.id}] {criterion.name}")
            elif cmd == "6":
                for criterion in app.criteria:
                    print(f"[{criterion.id}] {criterion.name}: "
                          f"максимум {criterion.max_score}, вес {criterion.weight}")
                if not app.criteria:
                    print("Критериев пока нет")
            elif cmd == "7":
                criterion_id = read_id("критерия")
                old = next((c for c in app.criteria if c.id == criterion_id), None)
                if old is None:
                    raise ValueError("Критерий не найден")
                name = input(f"Название [{old.name}]: ").strip() or old.name
                maximum = input(f"Максимум [{old.max_score}]: ").strip() or old.max_score
                weight = input(f"Вес [{old.weight}]: ").strip() or old.weight
                app.update_criterion(criterion_id, name, maximum, weight)
                print("Критерий обновлён")
            elif cmd == "8":
                app.remove_criterion(read_id("критерия"))
                print("Критерий удалён вместе с оценками")
            elif cmd == "9":
                student_id = read_id("студента")
                criterion_id = read_id("критерия")
                app.set_grade(student_id, criterion_id, input("Балл: "),
                              input("Комментарий (можно пустой): ").strip())
                print("Оценка сохранена")
            elif cmd == "10":
                rows = app.grades_for(read_id("студента"))
                for criterion, grade in rows:
                    if grade is None:
                        print(f"[{criterion.id}] {criterion.name}: нет оценки")
                    else:
                        print(f"[{criterion.id}] {criterion.name}: "
                              f"{grade.score.value}/{criterion.max_score} "
                              f"{grade.comment}")
                if not rows:
                    print("Критериев пока нет")
            elif cmd == "11":
                app.remove_grade(read_id("студента"), read_id("критерия"))
                print("Оценка удалена")
            elif cmd == "12":
                show_result(app.result_for(read_id("студента")))
            elif cmd == "13":
                for row in app.results():
                    show_result(row)
                if not app.students:
                    print("Студентов пока нет")
            elif cmd == "14":
                path = Path(input("Файл [итоги.csv]: ").strip() or "итоги.csv")
                app.export_results(path)
                print(f"Ведомость сохранена: {path}")
            else:
                print("Неизвестная команда")
        except ValueError as error:
            print(f"Ошибка: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход")
            return
        except OSError as error:
            print(f"Ошибка работы с файлом: {error}")


def main() -> None:
    try:
        run(Container().get_app())
    except (ValueError, OSError) as error:
        print(f"Не удалось открыть данные: {error}")


if __name__ == "__main__":
    main()
