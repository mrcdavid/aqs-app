"""Pricing math (v2), checked against worked examples (no database)."""

from dataclasses import replace
from decimal import Decimal as D
from typing import Literal

import pytest

from app.models import Basis, PriceUnit, PricingMethod
from app.services.pricing import (
    ComponentInput,
    area_sqft,
    basis_value,
    compute_price,
    money,
    round_up,
    to_inches,
    to_mm,
)


def line(
    basis: Basis,
    unit: PriceUnit,
    price: str,
    factor: str = "1",
    waste: str = "0",
    *,
    stock: tuple[str, str] | None = None,
    kind: Literal["material", "labor"] = "material",
) -> ComponentInput:
    return ComponentInput(
        kind=kind,
        code=f"X-{basis}-{unit}",
        name=f"{basis} {unit}",
        label="",
        basis=basis,
        unit=unit,
        unit_price=D(price),
        factor=D(factor),
        waste_percent=D(waste),
        stock_length=D(stock[0]) if stock else None,
        stock_length_unit=stock[1] if stock else None,
    )


# Sliding window 48 x 48 in = 16 sq ft, perimeter 16 ft, width 4 ft.
SLIDING_WINDOW = [
    line(Basis.AREA, PriceUnit.SQFT, "45", waste="5"),  # glass: 16 * 1.05 = 16.8 sq ft -> 756.00
    # frame + panel profile: 2 runs of 16 ft = 32 ft of 21-ft bars = 1.5238 -> 2 bars -> 3700.00
    line(Basis.PERIMETER, PriceUnit.BAR, "1850", factor="2", stock=("21", "ft")),
    line(Basis.WIDTH, PriceUnit.FT, "55", factor="2"),  # 2 tracks: 8 ft -> 440.00
    line(Basis.FIXED, PriceUnit.PIECE, "35", factor="4"),  # 4 rollers -> 140.00
    line(Basis.PERIMETER, PriceUnit.KG, "320", factor="0.05"),  # jamb rubber 0.8 kg -> 256.00
    line(Basis.AREA, PriceUnit.SQFT, "20", kind="labor"),  # labour 16 sq ft -> 320.00
]
COSTS = [D("756.00"), D("3700.00"), D("440.00"), D("140.00"), D("256.00"), D("320.00")]
SIZE = {"width_in": D(48), "height_in": D(48)}
PHP = {"vat_percent": D(12), "currency": "PHP"}


def test_computed_worked_example() -> None:
    b = compute_price(SLIDING_WINDOW, **SIZE, quantity=2, markup_percent=D(20), **PHP)
    assert b.pricing_method == "computed"
    assert b.area_sqft == D("16.00")
    assert [x.cost for x in b.lines] == COSTS
    assert b.unit_subtotal == D("5612.00")
    assert b.unit_price == D("6734.40")  # 5612 * 1.20
    assert b.subtotal == D("11224.00")
    assert b.markup == D("2244.80")
    assert b.net == D("13468.80")
    assert b.vat == D(0) and b.total == b.net  # prices include VAT: nothing is added
    assert b.vat_included == D("1443.09")  # 13468.80 * 12 / 112
    assert b.rounded_total == b.total  # rounding is off by default
    assert b.margin == D("2244.80")


def test_whole_bars_round_up() -> None:
    frame = compute_price(SLIDING_WINDOW[1:2], **SIZE, quantity=1, **PHP).lines[0]
    assert (frame.needed, frame.quantity, frame.cost) == (D("1.5238"), D(2), D("3700.00"))
    assert (frame.stock_length, frame.stock_length_unit) == (D(21), "ft")


def test_metre_bars_are_not_over_counted() -> None:
    """600 cm wide, 2 runs = 12 m of 6-m bars: exactly 2 bars, not 3 (m -> ft precision)."""
    runs = line(Basis.WIDTH, PriceUnit.BAR, "450", factor="2", stock=("6", "m"))
    width = to_inches(D(600), "cm")
    b = compute_price([runs], width_in=width, height_in=D(48), quantity=1, **PHP)
    assert (b.lines[0].needed, b.lines[0].quantity) == (D("2.0000"), D(2))


def test_grill_worked_example() -> None:
    """48 x 48 grill: 3.5 bars of 10 mm square bar (6 m) -> 4 bars + labour per grill."""
    grill = [
        line(Basis.AREA, PriceUnit.BAR, "450", factor="0.2188", stock=("6", "m")),  # bars/sq ft
        line(Basis.FIXED, PriceUnit.PIECE, "500", kind="labor"),
    ]
    b = compute_price(grill, **SIZE, quantity=1, markup_percent=D(20), rounding_step=D(100), **PHP)
    assert (b.lines[0].needed, b.lines[0].quantity) == (D("3.5008"), D(4))
    assert b.unit_subtotal == D("2300.00")  # 4 * 450 + 500
    assert b.unit_price == D("2760.00")
    assert b.rounded_total == D("2800.00")


def test_per_sqft_worked_example() -> None:
    """Window 48 x 48 in, 1/4 bronze 350/sq ft + open back 40/sq ft: 16 * 390 = 6,240 -> 6,300."""
    b = compute_price(
        SLIDING_WINDOW,
        **SIZE,
        quantity=1,
        method=PricingMethod.PER_SQFT,
        rates=[("Sliding window", D(0)), ("1/4 Bronze", D(350)), ("Open back", D(40))],
        markup_percent=D(20),  # ignored: the owner's rate is the selling price
        rounding_step=D(100),
        **PHP,
    )
    assert [(r.name, r.rate_per_sqft) for r in b.rates] == [
        ("1/4 Bronze", D(350)),
        ("Open back", D(40)),
    ]
    assert b.rate_per_sqft == D(390)
    assert b.unit_price == D("6240.00")
    assert (b.markup_percent, b.markup, b.vat) == (D(0), D(0), D(0))
    assert b.rounded_total == D("6300.00")
    assert b.vat_included == D("675.00")  # 6300 * 12 / 112
    assert b.unit_subtotal == D("5612.00")  # the template is the cost guide
    assert b.margin == D("688.00")
    assert b.warnings == []


def test_per_sqft_without_lines_or_rate() -> None:
    b = compute_price([], **SIZE, quantity=3, method=PricingMethod.PER_SQFT, **PHP)
    assert b.unit_price == D(0) and b.unit_subtotal == D(0)
    assert b.warnings == ["No rate per sq ft is set, so the price is 0"]
    b = compute_price(
        [], **SIZE, quantity=3, method=PricingMethod.PER_SQFT, rates=[("W", D(100))], **PHP
    )
    assert (b.unit_price, b.net) == (D("1600.00"), D("4800.00"))


def test_basis_values_in_feet() -> None:
    assert basis_value(Basis.AREA, D(36), D(48)) == D(12)  # sq ft
    assert basis_value(Basis.PERIMETER, D(36), D(48)) == D(14)  # ft
    assert basis_value(Basis.WIDTH, D(36), D(48)) == D(3)
    assert basis_value(Basis.HEIGHT, D(36), D(48)) == D(4)
    assert basis_value(Basis.FIXED, D(36), D(48)) == D(1)


def test_area_from_inches_and_cm() -> None:
    assert area_sqft(D(48), D(48)) == D("16.00")
    assert area_sqft(D("47.5"), D(36)) == D("11.88")  # 11.875
    # 120 x 100 cm = 1.2 m² = 12.9167 sq ft, from the exact inches (not rounded mm)
    assert area_sqft(to_inches(D(120), "cm"), to_inches(D(100), "cm")) == D("12.92")
    b = compute_price(
        [], width_in=to_inches(D(120), "cm"), height_in=to_inches(D(100), "cm"), quantity=1,
        method=PricingMethod.PER_SQFT, rates=[("W", D(100))], **PHP,
    )  # fmt: skip
    assert (b.width_in, b.height_in, b.width_mm, b.height_mm) == (
        D("47.24"),
        D("39.37"),
        1200,
        1000,
    )
    assert b.unit_price == D("1292.00")


@pytest.mark.parametrize(
    ("value", "unit", "mm"),
    [("120", "cm", 1200), ("120.04", "cm", 1200), ("120.05", "cm", 1201), ("48", "in", 1219)],
)
def test_unit_conversion(value: str, unit: str, mm: int) -> None:
    assert to_mm(D(value), unit) == mm  # type: ignore[arg-type]  # parametrized literals


@pytest.mark.parametrize(
    ("amount", "step", "expected"),
    [
        ("21423", "100", "21500.00"),  # the owner's example
        ("21500.00", "100", "21500.00"),  # already a multiple: unchanged
        ("21500.01", "100", "21600.00"),  # one centavo over still rounds up
        ("21523", "500", "22000.00"),
        ("21423", "1000", "22000.00"),
        ("11977.19", "1", "11978.00"),
        ("11977.19", "0", "11977.19"),  # 0 = rounding off
    ],
)
def test_round_up(amount: str, step: str, expected: str) -> None:
    assert round_up(D(amount), D(step)) == D(expected)


def test_rounded_total_is_never_below_total() -> None:
    b = compute_price(
        SLIDING_WINDOW, **SIZE, quantity=2, markup_percent=D(20), rounding_step=D(100), **PHP
    )
    assert b.total == D("13468.80")  # the exact price is kept for the admin breakdown
    assert (b.rounding, b.rounded_total) == (D("31.20"), D("13500.00"))
    assert b.vat_included == D("1446.43")  # of the rounded total: 13500 * 12 / 112


def test_money_rounds_half_up() -> None:
    assert money(D("2.345")) == D("2.35")
    assert money(D("2.344")) == D("2.34")


def test_rejects_empty_template_and_bad_sizes() -> None:
    with pytest.raises(ValueError, match="no components"):
        compute_price([], **SIZE, quantity=1, **PHP)
    with pytest.raises(ValueError, match="positive"):
        compute_price(SLIDING_WINDOW, width_in=D(0), height_in=D(48), quantity=1, **PHP)
    no_length = replace(SLIDING_WINDOW[1], stock_length=None)
    with pytest.raises(ValueError, match="bar length"):
        compute_price([no_length], **SIZE, quantity=1, **PHP)


def test_add_on_lines_are_priced_and_tagged() -> None:
    open_back = replace(
        line(Basis.PERIMETER, PriceUnit.FT, "90"), code="AL-OPENBACK", option="Open back"
    )
    base = compute_price(SLIDING_WINDOW, **SIZE, quantity=1, **PHP)
    extra = compute_price([*SLIDING_WINDOW, open_back], **SIZE, quantity=1, **PHP)
    assert all(x.option == "" for x in base.lines)
    assert extra.lines[-1].option == "Open back"
    assert extra.lines[-1].cost == D("1440.00")  # 16 ft around the window x 90
    assert extra.total == base.total + D("1440.00")  # grows with the size, like any line


def test_lines_can_be_measured_smaller() -> None:
    """Inside an open back frame the window is smaller than the opening typed."""
    glass = line(Basis.AREA, PriceUnit.SQFT, "100")
    inner = replace(glass, width_reduction_in=D(4), height_reduction_in=D(4))
    b = compute_price([glass, inner], **SIZE, quantity=1, **PHP)
    assert [(x.width_in, x.height_in) for x in b.lines] == [(D(48), D(48)), (D(44), D(44))]
    assert [x.cost for x in b.lines] == [D("1600.00"), D("1344.44")]  # 16 vs 13.4444 sq ft
    with pytest.raises(ValueError, match="too small"):
        compute_price([inner], width_in=D(4), height_in=D(48), quantity=1, **PHP)
