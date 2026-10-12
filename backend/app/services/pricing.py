"""Price calculation. Pure functions on Decimal: no DB, no floats.

    per component: quantity = basis_value * factor * (1 + waste% / 100)   (rounded to 4 dp)
                   cost     = quantity * unit_price                        (rounded to 2 dp)
    unit_subtotal = sum(cost)                      (internal cost of one piece)
    unit_price    = unit_subtotal * (1 + markup%)  (what the customer sees per piece)
    subtotal      = unit_subtotal * quantity       net    = unit_price * quantity
    markup        = net - subtotal                 vat    = net * vat%
    total         = net + vat
    rounded_total = total rounded UP to the next multiple of rounding_step (0 = no rounding)
All money is rounded half-up to centavos at each step shown above. Markup is applied per piece
so the customer's unit price x quantity always equals the amount shown. The rounded total is what
the customer is quoted; rounding is always up, in the shop's favour.
"""

from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.models import Basis, PriceUnit

LengthUnit = Literal["cm", "in"]

CENT = Decimal("0.01")
QTY = Decimal("0.0001")
MM_PER = {"cm": Decimal(10), "in": Decimal("25.4")}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def round_up(amount: Decimal, step: Decimal) -> Decimal:
    """Round up to the next multiple of `step`: 21,423 -> 21,500 for step 100. Step 0 = as is."""
    if step <= 0:
        return amount
    return money((amount / step).to_integral_value(rounding=ROUND_CEILING) * step)


def to_mm(value: Decimal, unit: LengthUnit) -> int:
    """Customer input (cm or inches) -> whole millimetres."""
    return int((value * MM_PER[unit]).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def basis_value(basis: Basis, width_mm: int, height_mm: int) -> Decimal:
    w = Decimal(width_mm) / 1000
    h = Decimal(height_mm) / 1000
    match basis:
        case Basis.AREA:
            return w * h
        case Basis.PERIMETER:
            return 2 * (w + h)
        case Basis.WIDTH:
            return w
        case Basis.HEIGHT:
            return h
        case Basis.FIXED:
            return Decimal(1)


@dataclass(frozen=True)
class ComponentInput:
    """A template line with its current price, detached from the ORM (also used for snapshots)."""

    kind: Literal["material", "labor"]
    code: str
    name: str
    label: str
    basis: Basis
    unit: PriceUnit
    unit_price: Decimal
    factor: Decimal
    waste_percent: Decimal
    option: str = ""  # add-on name; "" = always included


@dataclass(frozen=True)
class PriceLine:
    kind: str
    code: str
    name: str
    label: str
    basis: Basis
    unit: PriceUnit
    unit_price: Decimal
    quantity: Decimal
    cost: Decimal
    option: str = ""


@dataclass(frozen=True)
class PriceBreakdown:
    width_mm: int
    height_mm: int
    quantity: int
    lines: list[PriceLine]
    unit_subtotal: Decimal
    unit_price: Decimal
    subtotal: Decimal
    markup_percent: Decimal
    markup: Decimal
    net: Decimal
    vat_percent: Decimal
    vat: Decimal
    total: Decimal
    rounding_step: Decimal
    rounding: Decimal  # rounded_total - total
    rounded_total: Decimal
    currency: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_price(
    components: list[ComponentInput],
    *,
    width_mm: int,
    height_mm: int,
    quantity: int,
    markup_percent: Decimal,
    vat_percent: Decimal,
    currency: str,
    rounding_step: Decimal = Decimal(0),
) -> PriceBreakdown:
    if not components:
        raise ValueError("Product has no components")
    if width_mm <= 0 or height_mm <= 0 or quantity <= 0:
        raise ValueError("Dimensions and quantity must be positive")

    lines: list[PriceLine] = []
    for c in components:
        qty = (
            basis_value(c.basis, width_mm, height_mm) * c.factor * (1 + c.waste_percent / 100)
        ).quantize(QTY, rounding=ROUND_HALF_UP)
        lines.append(
            PriceLine(
                kind=c.kind,
                code=c.code,
                name=c.name,
                label=c.label,
                basis=c.basis,
                unit=c.unit,
                unit_price=c.unit_price,
                quantity=qty,
                cost=money(qty * c.unit_price),
                option=c.option,
            )
        )

    unit_subtotal = sum((line.cost for line in lines), Decimal(0))
    unit_price = money(unit_subtotal * (1 + markup_percent / 100))
    subtotal = unit_subtotal * quantity
    net = unit_price * quantity
    markup = net - subtotal
    vat = money(net * vat_percent / 100)
    total = net + vat
    rounded_total = round_up(total, rounding_step)
    return PriceBreakdown(
        width_mm=width_mm,
        height_mm=height_mm,
        quantity=quantity,
        lines=lines,
        unit_subtotal=unit_subtotal,
        unit_price=unit_price,
        subtotal=subtotal,
        markup_percent=markup_percent,
        markup=markup,
        net=net,
        vat_percent=vat_percent,
        vat=vat,
        total=total,
        rounding_step=rounding_step,
        rounding=rounded_total - total,
        rounded_total=rounded_total,
        currency=currency,
    )
