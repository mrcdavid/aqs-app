"""Price calculation. Pure functions on Decimal: no DB, no floats.

    per component: quantity = basis_value * factor * (1 + waste% / 100)   (rounded to 4 dp)
                   cost     = quantity * unit_price                        (rounded to 2 dp)
    unit_subtotal = sum(cost)                      (internal cost of one piece)
    unit_price    = unit_subtotal * (1 + markup%)  (what the customer sees per piece)
    subtotal      = unit_subtotal * quantity       net    = unit_price * quantity
    markup        = net - subtotal                 vat    = net * vat%
    total         = net + vat
All money is rounded half-up to centavos at each step shown above. Markup is applied per piece
so the customer's unit price x quantity always equals the amount shown.
"""

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from app.models import Basis, PriceUnit

LengthUnit = Literal["cm", "in"]

CENT = Decimal("0.01")
QTY = Decimal("0.0001")
MM_PER = {"cm": Decimal(10), "in": Decimal("25.4")}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


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
            )
        )

    unit_subtotal = sum((line.cost for line in lines), Decimal(0))
    unit_price = money(unit_subtotal * (1 + markup_percent / 100))
    subtotal = unit_subtotal * quantity
    net = unit_price * quantity
    markup = net - subtotal
    vat = money(net * vat_percent / 100)
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
        total=net + vat,
        currency=currency,
    )
