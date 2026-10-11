from math import fsum
from typing import Protocol

from models import EnergyConsumer, InventoryObject, Item, Vehicle


# Контракт техосмотра нужен, чтобы подменять его реализацию в тестах
class Inspector(Protocol):
    def inspect(self, vehicle: Vehicle) -> bool:
        pass


# Учебный техосмотр принимает транспорт с состоянием не ниже 5
class ServiceCenter:
    def inspect(self, vehicle: Vehicle) -> bool:
        return vehicle.condition >= 5


# Парк хранит принятый транспорт и вещи и предоставляет простые отчёты
class Fleet:
    # Зависимость от техосмотра передаётся снаружи по интерфейсу Inspector
    def __init__(self, inspector: Inspector) -> None:
        self._inspector = inspector
        self._vehicles: list[Vehicle] = []
        self._items: list[Item] = []

    def inventory(self) -> list[InventoryObject]:
        return [*self._vehicles, *self._items]

    def contains(self, number: str) -> bool:
        return any(obj.number == number for obj in self.inventory())

    # Один номер нельзя назначить одновременно транспорту и вещи
    def _check_number(self, number: str) -> None:
        if self.contains(number):
            raise ValueError(f"Номер {number} уже используется")

    # Не прошедший техосмотр транспорт не попадает в парк
    def add_vehicle(self, vehicle: Vehicle) -> bool:
        self._check_number(vehicle.number)
        if not self._inspector.inspect(vehicle):
            return False
        self._vehicles.append(vehicle)
        return True

    # Вещи ставятся на баланс без техосмотра транспорта
    def add_item(self, item: Item) -> None:
        self._check_number(item.number)
        self._items.append(item)

    def counts(self) -> tuple[int, int]:
        return len(self._vehicles), len(self._items)

    # Суммируются все объекты с интерфейсом EnergyConsumer
    def daily_energy(self) -> float:
        return fsum(
            obj.daily_kwh
            for obj in self.inventory()
            if isinstance(obj, EnergyConsumer)
        )

    # Для новичков доступны только принятые транспортные средства
    def for_beginners(self) -> list[Vehicle]:
        return [vehicle for vehicle in self._vehicles if vehicle.for_beginner()]
