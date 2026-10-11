from dataclasses import dataclass
from math import isfinite
from typing import ClassVar, Protocol, runtime_checkable


# Интерфейс любого объекта, который ставится на баланс
class InventoryObject(Protocol):
    @property
    def number(self) -> str:
        pass

    @property
    def name(self) -> str:
        pass

    @property
    def kind(self) -> str:
        pass


# Отдельный интерфейс для объектов, потребляющих электричество
@runtime_checkable
class EnergyConsumer(Protocol):
    @property
    def daily_kwh(self) -> float:
        pass


# Общая проверка расхода энергии для транспорта и вещей
# Нулевой расход разрешён, отрицательные и бесконечные значения запрещены
def check_energy(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Расход энергии должен быть числом")
    if not isfinite(value) or value < 0:
        raise ValueError("Расход энергии должен быть неотрицательным конечным числом")


# Базовая модель имущества с обязательными инвентарными данными
@dataclass(frozen=True)
class Asset:
    number: str
    name: str
    kind: ClassVar[str] = "Имущество"

    def __post_init__(self) -> None:
        if not isinstance(self.number, str) or not self.number.strip():
            raise ValueError("Укажите инвентарный номер")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Укажите название")


# Любой транспорт имеет простоту для новичка и оценку состояния
@dataclass(frozen=True)
class Vehicle(Asset):
    ease: int
    condition: int
    kind: ClassVar[str] = "Транспорт"

    def __post_init__(self) -> None:
        super().__post_init__()
        if any(type(value) is not int or not 1 <= value <= 10
               for value in (self.ease, self.condition)):
            raise ValueError("Простота и состояние должны быть целыми от 1 до 10")

    # По условию транспорт подходит новичку при простоте от 6
    def for_beginner(self) -> bool:
        return self.ease >= 6


# Электротранспорт дополнительно хранит суточный расход энергии
@dataclass(frozen=True)
class PoweredVehicle(Vehicle):
    daily_kwh: float

    def __post_init__(self) -> None:
        super().__post_init__()
        check_energy(self.daily_kwh)


# Конкретные виды транспорта отличаются наименованием и набором полей
class Scooter(PoweredVehicle):
    kind = "Электросамокат"


class ElectricBike(PoweredVehicle):
    kind = "Электровелосипед"


class Bicycle(Vehicle):
    kind = "Велосипед"


# Вещи учитываются на балансе, но не проходят техосмотр транспорта
class Item(Asset):
    kind = "Вещь"


class Helmet(Item):
    kind = "Шлем"


# Зарядная станция одновременно является вещью и потребителем энергии
@dataclass(frozen=True)
class ChargingStation(Item):
    daily_kwh: float
    kind: ClassVar[str] = "Зарядная станция"

    def __post_init__(self) -> None:
        super().__post_init__()
        check_energy(self.daily_kwh)


# Реестры определяют доступные типы в меню
# Для нового вида достаточно добавить класс и запись в нужный реестр
VEHICLE_TYPES: dict[str, type[Vehicle]] = {
    "1": Scooter,
    "2": Bicycle,
    "3": ElectricBike,
}
ITEM_TYPES: dict[str, type[Item]] = {
    "1": Helmet,
    "2": ChargingStation,
}
