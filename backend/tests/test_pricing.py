"""Pricing math, checked against a worked example (no database)."""

from decimal import Decimal as D

import pytest

from app.models import Basis, PriceUnit
from app.services.pricing import ComponentInput, basis_value, compute_price, money, to_mm


def line(basis: Basis, unit: PriceUnit, price: str, factor: str = "1", waste: str = "0"):
    return ComponentInput(
        kind="material",
        code=f"X-{basis}",
        name=str(basis),
        label="",
        basis=basis,
        unit=unit,
        unit_price=D(price),
        factor=D(factor),
        waste_percent=D(waste),
    )


# Sliding window 1200 x 1000 mm, quantity 2, markup 20%, VAT 12%.
SLIDING_WINDOW = [
    line(Basis.AREA, PriceUnit.SQM, "850", waste="5"),  # glass: 1.2 m² * 1.05 = 1.26 -> 1071.00
    line(Basis.PERIMETER, PriceUnit.LM, "420", waste="10"),  # frame: 4.4 m * 1.1 = 4.84 -> 2032.80
    line(Basis.WIDTH, PriceUnit.LM, "180", factor="2"),  # 2 tracks: 2.4 m -> 432.00
    line(Basis.FIXED, PriceUnit.PIECE, "35", factor="4"),  # 4 rollers -> 140.00
    line(Basis.AREA, PriceUnit.SQM, "650"),  # labour: 1.2 m² -> 780.00
]


def test_worked_example() -> None:
    b = compute_price(
        SLIDING_WINDOW,
        width_mm=1200,
        height_mm=1000,
        quantity=2,
        markup_percent=D("20"),
        vat_percent=D("12"),
        currency="PHP",
    )
    assert [line.cost for line in b.lines] == [
        D("1071.00"),
        D("2032.80"),
        D("432.00"),
        D("140.00"),
        D("780.00"),
    ]
    assert b.unit_subtotal == D("4455.80")
    assert b.unit_price == D("5346.96")  # 4455.80 * 1.20, what the customer sees per piece
    assert b.subtotal == D("8911.60")
    assert b.markup == D("1782.32")
    assert b.net == D("10693.92")
    assert b.vat == D("1283.27")  # 1283.2704 rounded
    assert b.total == D("11977.19")


def test_basis_values() -> None:
    assert basis_value(Basis.AREA, 1500, 2000) == D("3")
    assert basis_value(Basis.PERIMETER, 1500, 2000) == D("7")
    assert basis_value(Basis.WIDTH, 1500, 2000) == D("1.5")
    assert basis_value(Basis.HEIGHT, 1500, 2000) == D("2")
    assert basis_value(Basis.FIXED, 1500, 2000) == D("1")


@pytest.mark.parametrize(
    ("value", "unit", "mm"),
    [("120", "cm", 1200), ("120.04", "cm", 1200), ("120.05", "cm", 1201), ("48", "in", 1219)],
)
def test_unit_conversion(value: str, unit: str, mm: int) -> None:
    assert to_mm(D(value), unit) == mm  # type: ignore[arg-type]


def test_money_rounds_half_up() -> None:
    assert money(D("2.345")) == D("2.35")
    assert money(D("2.344")) == D("2.34")


def test_rejects_empty_template_and_bad_sizes() -> None:
    kwargs = {"markup_percent": D(0), "vat_percent": D(12), "currency": "PHP"}
    with pytest.raises(ValueError, match="no components"):
        compute_price([], width_mm=1000, height_mm=1000, quantity=1, **kwargs)
    with pytest.raises(ValueError, match="positive"):
        compute_price(SLIDING_WINDOW, width_mm=0, height_mm=1000, quantity=1, **kwargs)
