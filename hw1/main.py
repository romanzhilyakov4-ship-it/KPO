from collections.abc import Callable
from dataclasses import fields
from typing import TypeVar, cast

from models import ITEM_TYPES, VEHICLE_TYPES
from services import Fleet, Inspector, ServiceCenter

T = TypeVar("T")


# Простой DI-контейнер связывает интерфейсы с фабриками объектов
# В тестах фабрику техосмотра можно заменить на поддельную
class Container:
    def __init__(self) -> None:
        self._factories: dict[type, Callable[[], object]] = {}
        self.bind(Inspector, ServiceCenter)
        self.bind(Fleet, lambda: Fleet(self.get(Inspector)))

    def bind(self, contract: type[T], factory: Callable[[], T]) -> None:
        self._factories[contract] = factory

    def get(self, contract: type[T]) -> T:
        if contract not in self._factories:
            raise ValueError(f"Нет регистрации для {contract.__name__}")
        return cast(T, self._factories[contract]())


# Названия полей используются в подсказках для пользователя
# Для новых полей без записи здесь выводится имя поля из модели
FIELD_LABELS = {
    "number": "Инвентарный номер",
    "name": "Название",
    "ease": "Простота (1–10)",
    "condition": "Состояние (1–10)",
    "daily_kwh": "Расход кВт·ч/сутки",
}


# Пользователь выбирает тип из реестра без условий для каждого класса
def choose_type(types: dict[str, type[T]]) -> type[T]:
    for key, cls in types.items():
        print(f"{key}. {cls.kind}")
    key = input("Тип: ").strip()
    if key not in types:
        raise ValueError("Неизвестный тип")
    return types[key]


# Поля запрашиваются по описанию dataclass без проверки конкретного типа
# Новый транспорт с полем str, int или float не требует правок этого метода
def create_object(cls: type[T]) -> T:
    values = {}
    for field in fields(cls):
        prompt = FIELD_LABELS.get(field.name, field.name)
        raw = input(f"{prompt}: ").strip()
        if field.type not in (str, int, float):
            raise ValueError(f"Неподдерживаемый тип поля {field.name}")
        values[field.name] = field.type(raw)
    return cls(**values)


# Все решения о приёмке остаются в сервисе, а не в меню
def add_vehicle(fleet: Fleet) -> None:
    vehicle = create_object(choose_type(VEHICLE_TYPES))
    if fleet.add_vehicle(vehicle):
        print("Принят после техосмотра")
    else:
        print("Отклонён техосмотром")


# Добавление вещей выполняется отдельно от приёмки транспорта
def add_item(fleet: Fleet) -> None:
    item = create_object(choose_type(ITEM_TYPES))
    fleet.add_item(item)
    print("Вещь поставлена на баланс")


# Отчёты показывают количество имущества и его инвентарные номера
def report(fleet: Fleet) -> None:
    vehicles, items = fleet.counts()
    print(f"Транспорт: {vehicles}; вещи: {items}; всего: {vehicles + items}")
    for obj in fleet.inventory():
        print(f"[{obj.number}] {obj.kind}: {obj.name}")


# Список новичков строится по уже принятым транспортным средствам
def beginners(fleet: Fleet) -> None:
    print("Для новичков (простота ≥ 6):")
    for vehicle in fleet.for_beginners():
        print(f"[{vehicle.number}] {vehicle.kind}: {vehicle.name}, простота {vehicle.ease}")


# Ошибки ввода не закрывают приложение, пользователь возвращается в меню
def run(fleet: Fleet) -> None:
    while True:
        print(
            "\n1 — транспорт | 2 — вещь | 3 — парк | 4 — энергия | "
            "5 — новичкам | 0 — выход"
        )
        try:
            command = input("Команда: ").strip()
            if command == "0":
                return
            if command == "1":
                add_vehicle(fleet)
            elif command == "2":
                add_item(fleet)
            elif command == "3":
                report(fleet)
            elif command == "4":
                print(f"Энергия: {fleet.daily_energy():.2f} кВт·ч/сутки")
            elif command == "5":
                beginners(fleet)
            else:
                print("Неизвестная команда")
        except ValueError as error:
            print(f"Ошибка: {error}")
        except (EOFError, KeyboardInterrupt):
            print("\nВыход")
            return


# Точка входа получает готовый сервис из DI-контейнера
def main() -> None:
    run(Container().get(Fleet))


if __name__ == "__main__":
    main()
