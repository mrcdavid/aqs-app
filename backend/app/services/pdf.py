"""Quotation PDFs with ReportLab. Built only from the quotation snapshot, never from live prices.

Customer-facing: shows one amount (VAT included but never itemised), the 50/50 payment terms and
signature lines; never unit prices, internal costs, markup or VAT. All user-provided text is
escaped before it reaches ReportLab's markup parser.

Look: the app's Blue -> Indigo gradient (frontend/src/index.css) on the header band and the total,
slate text, soft rounded cards. Fonts are the built-in Helvetica family (no font files needed).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.quotations import DOWNPAYMENT_PERCENT, PHT, payment_split

# Same tokens as the web app (light theme).
BRAND = colors.HexColor("#2563eb")
INDIGO = colors.HexColor("#4f46e5")
BRAND_SOFT = colors.HexColor("#eff6ff")
BRAND_INK = colors.HexColor("#1e40af")
ON_BRAND = colors.HexColor("#dbeafe")  # soft white text on the gradient
INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
LINE_STRONG = colors.HexColor("#cbd5e1")
SURFACE_2 = colors.HexColor("#f8fafc")
DANGER = colors.HexColor("#dc2626")

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
BAND = 44 * mm  # gradient header height
PAD = 6  # ReportLab's frame padding (points) on each side
WIDTH = PAGE_W - 2 * MARGIN - 2 * PAD  # content width
LEFT, RIGHT = MARGIN + PAD, PAGE_W - MARGIN - PAD  # content edges, for drawing on the canvas
UNITS = {"cm": "cm", "in": "in"}


@dataclass(frozen=True)
class PdfInput:
    snapshot: dict[str, Any]
    business: dict[str, Any]
    reference: str  # quote number, or DRAFT-xxxxxxxx
    created_at: datetime
    valid_until: date | None
    total: Decimal  # what the customer pays (VAT included)
    draft: bool
    note: str | None = None


def _styles() -> dict[str, ParagraphStyle]:
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.5, textColor=MUTED)
    bold = ParagraphStyle("bold", parent=body, fontName="Helvetica-Bold")
    return {
        "body": body,
        "small": small,
        "bold": bold,
        "label": ParagraphStyle(
            "label", parent=small, fontName="Helvetica-Bold", fontSize=7, textColor=BRAND
        ),
        "name": ParagraphStyle("name", parent=bold, fontSize=11.5, leading=15),
        "item": ParagraphStyle("item", parent=bold, fontSize=10.5, leading=14),
        "choice": ParagraphStyle("choice", parent=body, fontSize=8.5, leading=11.5),
        "with": ParagraphStyle(
            "with", parent=bold, fontSize=8.5, leading=11.5, textColor=BRAND_INK
        ),
        "label_right": ParagraphStyle(
            "label_right",
            parent=small,
            fontName="Helvetica-Bold",
            fontSize=7,
            textColor=BRAND,
            alignment=TA_RIGHT,
        ),
        "right": ParagraphStyle("right", parent=body, alignment=TA_RIGHT),
        "right_bold": ParagraphStyle("right_bold", parent=bold, alignment=TA_RIGHT),
        "pay_amount": ParagraphStyle(
            "pay_amount", parent=bold, fontSize=13, leading=17, textColor=BRAND_INK
        ),
        "business": ParagraphStyle(
            "business",
            parent=bold,
            fontSize=18,
            leading=22,
            textColor=colors.white,
        ),
        "on_brand": ParagraphStyle(
            "on_brand", parent=body, fontSize=8.5, leading=11.5, textColor=ON_BRAND
        ),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """Paragraph from untrusted text: escaped, newlines kept."""
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _label(text: str, s: dict[str, ParagraphStyle]) -> Paragraph:
    """Small spaced capitals, e.g. PREPARED FOR (our own text, not user input)."""
    return Paragraph(f'<font name="Helvetica-Bold">{text.upper()}</font>', s["label"])


def _money(amount: str | Decimal, currency: str) -> str:
    return f"{currency} {Decimal(amount):,.2f}"


def _num(value: str) -> str:
    """ "120.00" -> "120", "47.25" -> "47.25"."""
    return format(Decimal(value).normalize(), "f")


def _date(d: date | datetime) -> str:
    if isinstance(d, datetime):
        d = d.astimezone(PHT).date()
    return d.strftime("%B %d, %Y").replace(" 0", " ")


def _card(rows: list[list[Any]], width: float, background: colors.Color = SURFACE_2) -> Table:
    """A soft rounded panel."""
    table = Table(rows, colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("ROUNDEDCORNERS", [8, 8, 8, 8]),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        )
    )
    return table


def _side_by_side(left: Any, right: Any, gap: float = 6 * mm) -> Table:
    half = (WIDTH - gap) / 2
    table = Table([[left, "", right]], colWidths=[half, gap, half])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


class GradientBanner(Flowable):
    """Rounded Blue -> Indigo bar with a label on the left and the amount on the right."""

    def __init__(self, label: str, amount: str, width: float, height: float = 16 * mm) -> None:
        super().__init__()
        self.label, self.amount = label, amount
        self.width, self.height = width, height

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, 0, self.width, self.height, 10)
        c.clipPath(path, stroke=0, fill=0)
        c.linearGradient(0, 0, self.width, self.height, (BRAND, INDIGO), extend=False)
        c.restoreState()
        c.saveState()
        c.setFillColor(ON_BRAND)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(14, self.height / 2 - 3, self.label.upper())
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 17)
        c.drawRightString(self.width - 14, self.height / 2 - 6, self.amount)
        c.restoreState()


def _spaced(canvas: Canvas, text: str, font: str, size: float, x_right: float, y: float) -> None:
    """Right-aligned letter-spaced text (canvas drawRightString can't space letters)."""
    space = 1.6
    width = canvas.stringWidth(text, font, size) + space * (len(text) - 1)
    canvas.saveState()  # the letter spacing must not leak into later text
    t = canvas.beginText(x_right - width, y)
    t.setFont(font, size)
    t.setCharSpace(space)
    t.textOut(text)
    canvas.drawText(t)
    canvas.restoreState()


def _header(canvas: Canvas, data: PdfInput, s: dict[str, ParagraphStyle]) -> None:
    top = PAGE_H
    canvas.saveState()
    band = canvas.beginPath()
    band.rect(0, top - BAND, PAGE_W, BAND)
    canvas.clipPath(band, stroke=0, fill=0)
    canvas.linearGradient(0, top - BAND, PAGE_W, top, (BRAND, INDIGO), extend=False)
    # Two faint circles for depth.
    canvas.setFillColor(colors.white)
    canvas.setFillAlpha(0.07)
    canvas.circle(PAGE_W - 30 * mm, top - 4 * mm, 34 * mm, stroke=0, fill=1)
    canvas.circle(PAGE_W - 8 * mm, top - 40 * mm, 20 * mm, stroke=0, fill=1)
    canvas.restoreState()

    # Business on the left (wraps if long).
    y = top - 13 * mm
    blocks = [_p(data.business.get("name") or "", s["business"])]
    for key in ("address", "contact"):
        if data.business.get(key):
            blocks.append(_p(data.business[key], s["on_brand"]))
    for block in blocks:
        _, h = block.wrapOn(canvas, 110 * mm, BAND)
        y -= h
        block.drawOn(canvas, LEFT, y)
        y -= 1.5 * mm

    # Document title and number on the right.
    canvas.saveState()
    canvas.setFillColor(ON_BRAND)
    title = "ESTIMATE" if data.draft else "QUOTATION"
    _spaced(canvas, title, "Helvetica-Bold", 9, RIGHT, top - 15 * mm)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawRightString(RIGHT, top - 23 * mm, data.reference)
    canvas.setFillColor(ON_BRAND)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(RIGHT, top - 29 * mm, _date(data.created_at))
    canvas.restoreState()


def _watermark(canvas: Canvas) -> None:
    """Drawn on top of the page (see _Document), see-through so the text stays readable."""
    canvas.saveState()
    canvas.setFillColor(DANGER)
    canvas.setFillAlpha(0.16)
    canvas.translate(PAGE_W / 2, PAGE_H / 2 - 20 * mm)
    canvas.rotate(32)
    canvas.setFont("Helvetica-Bold", 70)
    canvas.drawCentredString(0, 10, "ESTIMATE")
    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawCentredString(0, -26, "PENDING APPROVAL")
    canvas.restoreState()


class _Document(SimpleDocTemplate):
    """Draws the draft watermark after each page's content, so it sits in front of it."""

    def __init__(self, *args: Any, watermark: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.watermark = watermark

    def afterPage(self) -> None:  # noqa: N802 - ReportLab's hook name
        if self.watermark:
            _watermark(self.canv)


def _footer(canvas: Canvas, page: int) -> None:
    canvas.saveState()
    bar = canvas.beginPath()
    bar.rect(LEFT, 15 * mm, RIGHT - LEFT, 0.8 * mm)
    canvas.clipPath(bar, stroke=0, fill=0)
    canvas.linearGradient(LEFT, 15 * mm, RIGHT, 15 * mm, (BRAND, INDIGO), extend=False)
    canvas.restoreState()
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(LEFT, 10 * mm, "Generated by AQS APP - Automatic Quotation System")
    canvas.drawRightString(RIGHT, 10 * mm, f"Page {page}")
    canvas.restoreState()


def _signatures(owner: str, client: str, s: dict[str, ParagraphStyle]) -> KeepTogether:
    """Owner on the left, client (conforme) on the right, with room to sign above each line."""
    gap = 16 * mm
    half = (WIDTH - gap) / 2
    rows = [
        [_label("Prepared by", s), "", _label("Conforme", s)],
        ["", "", ""],
        [_p(owner, s["bold"]), "", _p(client, s["bold"])],
        [
            Paragraph("Owner", s["small"]),
            "",
            Paragraph("Client - signature over printed name", s["small"]),
        ],
        ["", "", Paragraph("Date: ______________________", s["small"])],
    ]
    table = Table(rows, colWidths=[half, gap, half], rowHeights=[None, 15 * mm, None, None, 9 * mm])
    table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 2), (0, 2), 0.8, LINE_STRONG),
                ("LINEABOVE", (2, 2), (2, 2), 0.8, LINE_STRONG),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )
    return KeepTogether([table])


def render_quotation_pdf(data: PdfInput) -> bytes:
    s = _styles()
    snap = data.snapshot
    pricing = snap["pricing"]
    currency = pricing["currency"]
    customer = snap["customer"]
    product = snap["product"]
    inp = snap["input"]
    unit = UNITS.get(inp["unit"], inp["unit"])
    half = (WIDTH - 6 * mm) / 2
    story: list[Any] = []

    # Who it's for, and the document details.
    contact = "  |  ".join(v for v in (customer["contact_number"], customer["email"]) if v)
    client_card = _card(
        [
            [_label("Prepared for", s)],
            [_p(customer["full_name"], s["name"])],
            [_p(customer["address_line"], s["body"])],
            [_p(f"{customer['city']}, {customer['province']}", s["body"])],
            [_p(contact, s["small"])],
        ],
        half,
    )
    details = [
        ("Quotation no.", data.reference),
        ("Date", _date(data.created_at)),
        ("Valid until", _date(data.valid_until) if data.valid_until else "Issued upon approval"),
    ]
    details_table = Table(
        [[Paragraph(k, s["small"]), _p(v, s["right_bold"])] for k, v in details],
        colWidths=[(half - 24) * 0.42, (half - 24) * 0.58],
    )
    details_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    details_card = _card([[_label("Details", s)], [details_table]], half)
    story += [_side_by_side(client_card, details_card), Spacer(1, 7 * mm)]

    # What is being made: no prices per line.
    includes = ", ".join(
        line["label"] or line["name"] for line in pricing["lines"] if not line.get("option")
    )
    description: list[Any] = [_p(product["name"], s["item"])]
    if product.get("description"):
        description.append(_p(product["description"], s["small"]))
    description.append(_p(f"Includes: {includes}", s["small"]))
    for choice in snap.get("choices", []):
        description.append(_p(f"{choice['group']}: {choice['name']}", s["choice"]))
    if add_ons := [o["name"] for o in snap.get("options", [])]:
        description.append(_p(f"With: {', '.join(add_ons)}", s["with"]))
    size = [
        _p(f"{_num(inp['width'])} x {_num(inp['height'])} {unit}", s["bold"]),
        _p(f"{pricing['width_mm']} x {pricing['height_mm']} mm", s["small"]),
    ]
    items = Table(
        [
            [_label("Description", s), _label("Size", s), Paragraph("QTY", s["label_right"])],
            [description, size, _p(str(pricing["quantity"]), s["right_bold"])],
        ],
        colWidths=[WIDTH - 62 * mm, 44 * mm, 18 * mm],
    )
    items.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINE_STRONG),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINE),
            ]
        )
    )
    story += [items, Spacer(1, 5 * mm)]

    # One amount: VAT is included but not shown.
    label = "Estimated amount" if data.draft else "Total amount"
    story += [GradientBanner(label, _money(data.total, currency), WIDTH), Spacer(1, 6 * mm)]

    # Payment terms as two cards.
    downpayment, balance = payment_split(data.total)
    down_pct = _num(str(DOWNPAYMENT_PERCENT))
    rest_pct = _num(str(100 - DOWNPAYMENT_PERCENT))
    pay_cards = [
        _card(
            [[_label(f"{pct}% {when}", s)], [_p(_money(amount, currency), s["pay_amount"])]],
            half,
            BRAND_SOFT,
        )
        for pct, when, amount in (
            (down_pct, "downpayment", downpayment),
            (rest_pct, "upon completion and installation", balance),
        )
    ]
    story += [_label("Payment terms", s), Spacer(1, 2 * mm), _side_by_side(*pay_cards)]

    if data.note:
        story += [
            Spacer(1, 6 * mm),
            _label("Note", s),
            Spacer(1, 1.5 * mm),
            _p(data.note, s["body"]),
        ]
    if data.business.get("terms"):
        story += [
            Spacer(1, 6 * mm),
            _label("Terms and conditions", s),
            Spacer(1, 1.5 * mm),
            _p(data.business["terms"], s["small"]),
        ]
    story += [
        Spacer(1, 12 * mm),
        _signatures(data.business.get("owner_name") or "", customer["full_name"], s),
    ]

    buffer = BytesIO()
    doc = _Document(
        buffer,
        watermark=data.draft,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=BAND + 8 * mm,
        bottomMargin=22 * mm,
        title=f"{'Estimate' if data.draft else 'Quotation'} {data.reference}",
        author=data.business.get("name") or "AQS APP",
    )

    def on_page(canvas: Canvas, d: Any) -> None:
        _header(canvas, data, s)
        _footer(canvas, d.page)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buffer.getvalue()
