"""Price calculation (pricing v2). Pure functions on Decimal: no DB, no floats.

Sizes are worked out in inches from what was typed (cm / 2.54, never via rounded mm); lengths
are in feet and areas in square feet:

    area_sqft = width_in * height_in / 144                                    (2 dp)

Template lines (materials and labour, each in the unit it is bought or paid in):
    quantity = basis_value * factor * (1 + waste% / 100)                       (4 dp)
      bars: whole bars, rounded up. A length basis is divided by the bar's stock length
            (32 ft of profile in 21-ft bars -> 1.5238 -> 2 bars); an area basis takes
            factor = bars per sq ft (grills); fixed = factor bars.
    cost     = quantity * unit_price                                            (2 dp)
    unit_subtotal = sum(cost)          the cost of one piece (for per-sq-ft products: a guide)

Price of one piece, by the product's pricing method:
    per_sqft: unit_price = area_sqft * (product rate + chosen options' rates)
    computed: unit_price = unit_subtotal * (1 + markup%)
    net = unit_price * quantity;  rounded_total = net rounded UP to the next rounding_step

Prices are final: VAT is included, never added (vat = 0, total = net). `vat_included` is the VAT
inside the rounded total and `margin` = rounded_total - unit_subtotal * quantity; staff only.
Snapshots priced before v2 have no `pricing_method`: metric units and VAT added on top.
All money is rounded half-up to centavos; the final rounding is always up, in the shop's favour.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.models import Basis, PriceUnit, PricingMethod
from app.models.catalog import LENGTHS

LengthUnit = Literal["cm", "in"]

CENT = Decimal("0.01")
QTY = Decimal("0.0001")
MM_PER = {"cm": Decimal(10), "in": Decimal("25.4")}
CM_PER_IN = Decimal("2.54")
MM_PER_IN = Decimal("25.4")
M_PER_FT = Decimal("0.3048")
SQIN_PER_SQFT = Decimal(144)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def round_up(amount: Decimal, step: Decimal) -> Decimal:
    """Round up to the next multiple of `step`: 21,423 -> 21,500 for step 100. Step 0 = as is."""
    if step <= 0:
        return amount
    return money((amount / step).to_integral_value(rounding=ROUND_CEILING) * step)


def to_mm(value: Decimal, unit: LengthUnit) -> int:
    """Customer input (cm or inches) -> whole millimetres (stored, and checked against limits)."""
    return int((value * MM_PER[unit]).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_inches(value: Decimal, unit: LengthUnit) -> Decimal:
    """Customer input -> exact inches (what prices are worked out from)."""
    return value if unit == "in" else value / CM_PER_IN


def mm_to_inches(mm: int) -> Decimal:
    return Decimal(mm) / MM_PER_IN


def area_sqft(width_in: Decimal, height_in: Decimal) -> Decimal:
    return money(width_in * height_in / SQIN_PER_SQFT)


def basis_value(basis: Basis, width_in: Decimal, height_in: Decimal) -> Decimal:
    """Area in sq ft, lengths in ft, fixed = 1."""
    match basis:
        case Basis.AREA:
            return width_in * height_in / SQIN_PER_SQFT
        case Basis.PERIMETER:
            return 2 * (width_in + height_in) / 12
        case Basis.WIDTH:
            return width_in / 12
        case Basis.HEIGHT:
            return height_in / 12
        case Basis.FIXED:
            return Decimal(1)


def stock_length_ft(length: Decimal, unit: str) -> Decimal:
    return length if unit == "ft" else length / M_PER_FT


@dataclass(frozen=True)
class ComponentInput:
    """A template line with its current price, detached from the ORM (also used for snapshots)."""

    kind: Literal["material", "labor"]
    code: str
    name: str
    label: str
    basis: Basis
    unit: PriceUnit
    unit_price: Decimal  # bars: price of one whole bar
    factor: Decimal
    waste_percent: Decimal
    option: str = ""  # add-on or choice name; "" = always included
    stock_length: Decimal | None = None  # bars only: e.g. 21 (ft) or 6 (m)
    stock_length_unit: str | None = None
    width_reduction_in: Decimal = Decimal(0)  # measure this line narrower than the size typed
    height_reduction_in: Decimal = Decimal(0)


@dataclass(frozen=True)
class PriceLine:
    kind: str
    code: str
    name: str
    label: str
    basis: Basis
    unit: str
    unit_price: Decimal
    quantity: Decimal  # in the line's unit; bars: whole bars
    cost: Decimal
    option: str = ""
    needed: Decimal | None = None  # bars only: before rounding up to whole bars
    stock_length: Decimal | None = None
    stock_length_unit: str | None = None
    width_in: Decimal = Decimal(0)  # the size this line was measured at
    height_in: Decimal = Decimal(0)


@dataclass(frozen=True)
class RateLine:
    """Per-sq-ft products: one part of the selling rate (the product's own, or a chosen option)."""

    name: str
    rate_per_sqft: Decimal


@dataclass(frozen=True)
class PriceBreakdown:
    pricing_method: str
    width_mm: int
    height_mm: int
    width_in: Decimal
    height_in: Decimal
    area_sqft: Decimal
    quantity: int
    lines: list[PriceLine]
    rates: list[RateLine]
    rate_per_sqft: Decimal  # sum of `rates` (per-sq-ft products; 0 otherwise)
    unit_subtotal: Decimal  # cost of one piece
    unit_price: Decimal  # selling price of one piece
    subtotal: Decimal  # cost of all pieces
    markup_percent: Decimal
    markup: Decimal
    net: Decimal
    vat_percent: Decimal
    vat: Decimal  # VAT added on top: always 0 since v2 (prices include VAT)
    total: Decimal
    rounding_step: Decimal
    rounding: Decimal  # rounded_total - total
    rounded_total: Decimal
    vat_included: Decimal
    margin: Decimal
    currency: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        del data["warnings"]
        return data


def _line(c: ComponentInput, width_in: Decimal, height_in: Decimal) -> PriceLine:
    w, h = width_in - c.width_reduction_in, height_in - c.height_reduction_in
    if w <= 0 or h <= 0:
        raise ValueError("The size is too small for the chosen options")
    raw = basis_value(c.basis, w, h) * c.factor * (1 + c.waste_percent / 100)
    needed = None
    if c.unit == PriceUnit.BAR:
        if not c.stock_length or not c.stock_length_unit:
            raise ValueError(f"{c.code} needs a bar length")
        if c.basis in LENGTHS:
            raw /= stock_length_ft(c.stock_length, c.stock_length_unit)
        # 4 dp first, so 2.00000001 bars (from the m -> ft division) stays 2 bars.
        needed = raw.quantize(QTY, rounding=ROUND_HALF_UP)
        qty = needed.to_integral_value(rounding=ROUND_CEILING).quantize(QTY)
    else:
        qty = raw.quantize(QTY, rounding=ROUND_HALF_UP)
    return PriceLine(
        kind=c.kind,
        code=c.code,
        name=c.name,
        label=c.label,
        basis=c.basis,
        unit=c.unit.value,
        unit_price=c.unit_price,
        quantity=qty,
        cost=money(qty * c.unit_price),
        option=c.option,
        needed=needed,
        stock_length=c.stock_length if c.unit == PriceUnit.BAR else None,
        stock_length_unit=c.stock_length_unit if c.unit == PriceUnit.BAR else None,
        width_in=money(w),
        height_in=money(h),
    )


def compute_price(
    components: Sequence[ComponentInput],
    *,
    width_in: Decimal,
    height_in: Decimal,
    quantity: int,
    vat_percent: Decimal,
    currency: str,
    method: PricingMethod = PricingMethod.COMPUTED,
    rates: Sequence[tuple[str, Decimal]] = (),
    markup_percent: Decimal = Decimal(0),
    rounding_step: Decimal = Decimal(0),
) -> PriceBreakdown:
    """`rates`: per-sq-ft products only, (name, rate per sq ft) - the product's own rate first,
    then each chosen option's extra. `markup_percent`: computed products only."""
    if width_in <= 0 or height_in <= 0 or quantity <= 0:
        raise ValueError("Dimensions and quantity must be positive")
    if method == PricingMethod.COMPUTED and not components:
        raise ValueError("This product has no components for these options")

    lines = [_line(c, width_in, height_in) for c in components]
    area = area_sqft(width_in, height_in)
    unit_subtotal = sum((line.cost for line in lines), Decimal(0))
    rate_lines = [RateLine(name, rate) for name, rate in rates if rate > 0]
    rate = sum((r.rate_per_sqft for r in rate_lines), Decimal(0))
    if method == PricingMethod.PER_SQFT:
        markup_percent = Decimal(0)
        unit_price = money(area * rate)
    else:
        rate_lines, rate = [], Decimal(0)
        unit_price = money(unit_subtotal * (1 + markup_percent / 100))

    subtotal = unit_subtotal * quantity
    net = unit_price * quantity
    markup = net - subtotal if method == PricingMethod.COMPUTED else Decimal(0)
    rounded_total = round_up(net, rounding_step)
    warnings = []
    if method == PricingMethod.PER_SQFT and rate <= 0:
        warnings.append("No rate per sq ft is set, so the price is 0")
    return PriceBreakdown(
        pricing_method=method.value,
        width_mm=int((width_in * MM_PER_IN).quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        height_mm=int((height_in * MM_PER_IN).quantize(Decimal(1), rounding=ROUND_HALF_UP)),
        width_in=money(width_in),
        height_in=money(height_in),
        area_sqft=area,
        quantity=quantity,
        lines=lines,
        rates=rate_lines,
        rate_per_sqft=rate,
        unit_subtotal=unit_subtotal,
        unit_price=unit_price,
        subtotal=subtotal,
        markup_percent=markup_percent,
        markup=markup,
        net=net,
        vat_percent=vat_percent,
        vat=Decimal("0.00"),
        total=net,
        rounding_step=rounding_step,
        rounding=rounded_total - net,
        rounded_total=rounded_total,
        vat_included=money(rounded_total * vat_percent / (100 + vat_percent)),
        margin=rounded_total - subtotal,
        currency=currency,
        warnings=warnings,
    )
