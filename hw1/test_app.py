# Поведенческие тесты на pytest с подменой техосмотра через DI

from collections.abc import Callable
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

import main
from models import (
    Bicycle, ChargingStation, ElectricBike, Helmet, Item, Scooter,
    ITEM_TYPES, VEHICLE_TYPES,
)
from services import Fleet, Inspector, ServiceCenter


def scooter(number: str = "S-1", ease: int = 6, condition: int = 7) -> Scooter:
    return Scooter(number, "Ninebot", ease, condition, 2.5)


def run_commands(monkeypatch: pytest.MonkeyPatch, *answers: str) -> None:
    responses = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _="": next(responses))
    main.main()


# Граничные значения техосмотра и подмена его реализации
@pytest.mark.parametrize("condition,accepted", [(4, False), (5, True), (10, True)])
def test_inspection_threshold(condition: int, accepted: bool) -> None:
    assert ServiceCenter().inspect(scooter(condition=condition)) is accepted


@pytest.mark.parametrize("accepted", [False, True])
def test_inspector_replaced_through_container(accepted: bool) -> None:
    fake = Mock(spec=ServiceCenter)
    fake.inspect.return_value = accepted
    container = main.Container()
    # Подмена реализации техосмотра выполняется через DI-контейнер
    container.bind(Inspector, lambda: fake)
    fleet = container.get(Fleet)

    vehicle = scooter()
    assert fleet.add_vehicle(vehicle) is accepted
    fake.inspect.assert_called_once_with(vehicle)
    assert fleet.counts() == (int(accepted), 0)


def test_rejected_vehicle_is_not_on_balance() -> None:
    fleet = Fleet(ServiceCenter())
    assert not fleet.add_vehicle(scooter(condition=2))
    assert fleet.inventory() == []
    assert fleet.daily_energy() == 0
    # Отклонённое устройство не занимает инвентарный номер
    assert fleet.add_vehicle(scooter(condition=5))


# Один инвентарный номер не может принадлежать двум объектам
def test_unique_number_among_vehicles_and_items() -> None:
    fleet = Fleet(ServiceCenter())
    fleet.add_vehicle(scooter())
    with pytest.raises(ValueError, match="уже используется"):
        fleet.add_item(Helmet("S-1", "Шлем"))
    fleet.add_item(Helmet("H-1", "Шлем"))
    with pytest.raises(ValueError, match="уже используется"):
        fleet.add_vehicle(scooter("H-1"))
    assert fleet.counts() == (1, 1)


# В энергопотреблении учитываются транспорт и вещи с общим интерфейсом
def test_daily_energy_includes_charging_and_ignores_regular_objects() -> None:
    fleet = Fleet(ServiceCenter())
    fleet.add_vehicle(scooter())
    fleet.add_vehicle(Bicycle("B-1", "Велосипед", 9, 9))
    fleet.add_vehicle(ElectricBike("E-1", "Электробайк", 3, 9, 3.0))
    fleet.add_item(Helmet("H-1", "Шлем"))
    fleet.add_item(ChargingStation("C-1", "Зарядная станция", 1.0))
    assert fleet.counts() == (3, 2)
    assert fleet.daily_energy() == pytest.approx(6.5)
    assert [(x.number, x.kind) for x in fleet.inventory()] == [
        ("S-1", "Электросамокат"), ("B-1", "Велосипед"),
        ("E-1", "Электровелосипед"), ("H-1", "Шлем"),
        ("C-1", "Зарядная станция"),
    ]


# Проверка границы правила для новичков и исключения отклонённого транспорта
@pytest.mark.parametrize("ease,expected", [(1, False), (5, False), (6, True), (10, True)])
def test_beginner_threshold(ease: int, expected: bool) -> None:
    assert scooter(ease=ease).for_beginner() is expected


def test_beginners_only_accepted_vehicles() -> None:
    fleet = Fleet(ServiceCenter())
    fleet.add_vehicle(scooter("S-1", 6, 7))
    fleet.add_vehicle(scooter("S-2", 5, 7))
    # Третий самокат не пройдёт техосмотр
    fleet.add_vehicle(scooter("S-3", 9, 3))
    fleet.add_item(Helmet("H-1", "Шлем"))
    assert [v.number for v in fleet.for_beginners()] == ["S-1"]


# Проверка ограничений доменных моделей
@pytest.mark.parametrize("factory", [
    lambda: Scooter("", "Ninebot", 8, 7, 1.0),
    lambda: Helmet("H-1", ""),
    lambda: Bicycle("B-1", "Велосипед", 0, 5),
    lambda: Bicycle("B-1", "Велосипед", 6, 11),
    lambda: Bicycle("B-1", "Велосипед", True, 8),
    lambda: Scooter("S-1", "Ninebot", 6, 5, -1.0),
    lambda: ChargingStation("C-1", "Зарядка", float("inf")),
])
def test_invalid_model_data(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


def test_zero_energy_is_allowed() -> None:
    assert ChargingStation("C-1", "Зарядка", 0).daily_kwh == 0


def test_missing_container_registration() -> None:
    with pytest.raises(ValueError, match="Нет регистрации"):
        main.Container().get(str)


# Полный сценарий: добавление транспорта и вещей, затем отчёты
def test_console_menu_scenario(monkeypatch: pytest.MonkeyPatch,
                               capsys: pytest.CaptureFixture[str]) -> None:
    run_commands(
        monkeypatch,
        "1", "1", "S-1", "Ninebot", "8", "9", "2.5",
        "2", "2", "C-1", "Зарядка", "1.0",
        "3", "4", "5", "0",
    )
    out = capsys.readouterr().out
    assert "Принят после техосмотра" in out
    assert "Вещь поставлена на баланс" in out
    assert "Транспорт: 1; вещи: 1; всего: 2" in out
    assert "[S-1] Электросамокат: Ninebot" in out
    assert "[C-1] Зарядная станция: Зарядка" in out
    assert "Энергия: 3.50" in out
    assert "Для новичков" in out


@pytest.mark.parametrize("vehicle_input,kind", [
    (("2", "B-1", "Велосипед", "6", "9"), "Велосипед"),
    (("3", "E-1", "Электробайк", "6", "9", "3"), "Электровелосипед"),
])
def test_console_other_transport_types(monkeypatch: pytest.MonkeyPatch,
                                       capsys: pytest.CaptureFixture[str],
                                       vehicle_input: tuple[str, ...], kind: str) -> None:
    run_commands(monkeypatch, "1", *vehicle_input, "3", "0")
    assert kind in capsys.readouterr().out


def test_console_helmet(monkeypatch: pytest.MonkeyPatch,
                        capsys: pytest.CaptureFixture[str]) -> None:
    run_commands(monkeypatch, "2", "1", "H-1", "Шлем", "3", "0")
    assert "[H-1] Шлем: Шлем" in capsys.readouterr().out


def test_console_handles_errors_without_crashing(monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    run_commands(monkeypatch, "x", "1", "99", "2", "1", "H-1", "", "3", "0")
    out = capsys.readouterr().out
    assert "Неизвестная команда" in out
    assert "Ошибка: Неизвестный тип" in out
    assert "Ошибка: Укажите название" in out
    assert "всего: 0" in out


def test_console_rejected_vehicle(monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture[str]) -> None:
    run_commands(monkeypatch, "1", "2", "B-1", "Неисправный", "7", "2", "3", "0")
    out = capsys.readouterr().out
    assert "Отклонён техосмотром" in out
    assert "всего: 0" in out


# Полный интерактивный сценарий заменяет демонстрацию со встроенными данными
# Проверяются приёмка, отказ, повторный номер, отчёты и правило для новичков
def test_console_all_scenarios_from_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_commands(
        monkeypatch,
        "1", "1", "S-1", "Ninebot", "8", "9", "2.5",
        "1", "2", "B-FAIL", "Неисправный", "7", "3",
        "1", "3", "E-1", "Электровелосипед", "4", "8", "3.0",
        "1", "2", "B-1", "Городской велосипед", "6", "7",
        "2", "1", "H-1", "Шлем",
        "2", "2", "C-1", "Зарядка", "1.0",
        "2", "1", "S-1", "Повторный номер",
        "3", "4", "5", "0",
    )
    out = capsys.readouterr().out
    assert out.count("Принят после техосмотра") == 3
    assert "Отклонён техосмотром" in out
    assert "Ошибка: Номер S-1 уже используется" in out
    assert "Транспорт: 3; вещи: 2; всего: 5" in out
    assert "Энергия: 6.50" in out
    assert "[S-1] Электросамокат: Ninebot, простота 8" in out
    assert "[B-1] Велосипед: Городской велосипед, простота 6" in out
    assert "[E-1] Электровелосипед: Электровелосипед, простота 4" not in out


# Новый наследник существующего транспорта регистрируется без правок меню
def test_new_transport_requires_only_model_registration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Tricycle(Bicycle):
        kind = "Трёхколёсный велосипед"

    monkeypatch.setitem(VEHICLE_TYPES, "4", Tricycle)
    run_commands(monkeypatch, "1", "4", "T-1", "Трайк", "7", "8", "3", "0")
    out = capsys.readouterr().out
    assert "4. Трёхколёсный велосипед" in out
    assert "[T-1] Трёхколёсный велосипед: Трайк" in out


@pytest.mark.parametrize("signal", [EOFError, KeyboardInterrupt])
def test_console_exits_cleanly_on_interrupted_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    signal: type[BaseException],
) -> None:
    def interrupted_input(_prompt: str = "") -> str:
        raise signal()

    monkeypatch.setattr("builtins.input", interrupted_input)
    main.run(Fleet(ServiceCenter()))
    assert "Выход" in capsys.readouterr().out


# Дополнительное поле транспорта должно автоматически появиться в меню
# Это проверяет расширяемость без изменения create_object и add_vehicle
def test_new_vehicle_with_extra_field(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @dataclass(frozen=True)
    class CargoBicycle(Bicycle):
        capacity: int
        kind = "Грузовой велосипед"

    monkeypatch.setitem(VEHICLE_TYPES, "4", CargoBicycle)
    prompts = []
    answers = iter(("1", "4", "B-7", "Грузовой", "7", "9", "20", "3", "0"))

    # Записываем приглашения к вводу для проверки нового поля
    def input_with_log(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", input_with_log)
    main.main()
    output = capsys.readouterr().out
    assert "capacity: " in prompts
    assert "[B-7] Грузовой велосипед: Грузовой" in output


# Новый энергопотребляющий инвентарь учитывается без правок Fleet
# Консоль автоматически запрашивает его дополнительное поле
def test_new_energy_consuming_item(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    @dataclass(frozen=True)
    class PowerCabinet(Item):
        daily_kwh: float
        kind = "Зарядный шкаф"

    monkeypatch.setitem(ITEM_TYPES, "3", PowerCabinet)
    run_commands(monkeypatch, "2", "3", "P-1", "Шкаф", "4.5", "4", "0")
    output = capsys.readouterr().out
    assert "Вещь поставлена на баланс" in output
    assert "Энергия: 4.50" in output


# Ошибочный числовой ввод не должен завершать всю программу
def test_console_bad_number_keeps_menu_running(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_commands(monkeypatch, "1", "2", "B-8", "Велосипед", "не число", "3", "0")
    output = capsys.readouterr().out
    assert "Ошибка:" in output
    assert "всего: 0" in output
