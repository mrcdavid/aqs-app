"""Turn stored quotations into API responses and PDFs (shared by customer and admin routes)."""

import logging

from fastapi import HTTPException, status
from fastapi.responses import Response

from app.models import PricingSettings, Quotation, QuotationStatus
from app.schemas.catalog import PricePreviewOut
from app.schemas.quotation import (
    AdminQuotationOut,
    AdminQuotationSummaryOut,
    QuotationOut,
    QuotationSummaryOut,
)
from app.services.pdf import PdfInput, render_quotation_pdf
from app.services.quotations import business_snapshot, read_pdf, save_pdf

logger = logging.getLogger("aqs.quotations")


def summary(q: Quotation) -> QuotationSummaryOut:
    return QuotationSummaryOut(
        id=q.id,
        number=q.number,
        status=q.status,
        product_name=q.snapshot["product"]["name"],
        width_mm=q.width_mm,
        height_mm=q.height_mm,
        quantity=q.quantity,
        total=q.total,
        currency=q.currency,
        created_at=q.created_at,
    )


def admin_summary(q: Quotation) -> AdminQuotationSummaryOut:
    customer = q.snapshot["customer"]
    return AdminQuotationSummaryOut(
        **summary(q).model_dump(),
        customer_name=customer["full_name"],
        customer_email=customer["email"],
        customer_city=q.customer_city,
        customer_province=q.customer_province,
    )


def customer_view(q: Quotation) -> QuotationOut:
    snap = q.snapshot
    pricing = snap["pricing"]
    return QuotationOut(
        id=q.id,
        number=q.number,
        status=q.status,
        product_name=snap["product"]["name"],
        product_description=snap["product"]["description"],
        includes=[line["label"] or line["name"] for line in pricing["lines"]],
        input_width=q.input_width,
        input_height=q.input_height,
        input_unit=q.input_unit,
        width_mm=q.width_mm,
        height_mm=q.height_mm,
        quantity=q.quantity,
        unit_price=pricing["unit_price"],
        amount=pricing["net"],
        vat_percent=pricing["vat_percent"],
        vat=pricing["vat"],
        total=pricing["total"],
        currency=pricing["currency"],
        created_at=q.created_at,
        reviewed_at=q.reviewed_at,
        review_note=q.review_note,
        valid_until=q.valid_until,
        can_cancel=q.status == QuotationStatus.PENDING,
    )


def admin_view(q: Quotation, reviewed_by_email: str | None) -> AdminQuotationOut:
    return AdminQuotationOut(
        **customer_view(q).model_dump(),
        customer=q.snapshot["customer"],
        reviewed_by_email=reviewed_by_email,
        breakdown=PricePreviewOut(**q.snapshot["pricing"], warnings=[]),
    )


def render_final(q: Quotation) -> bytes:
    assert q.number and q.valid_until
    return render_quotation_pdf(
        PdfInput(
            snapshot=q.snapshot,
            business=q.snapshot.get("business", {}),
            reference=q.number,
            created_at=q.reviewed_at or q.created_at,
            valid_until=q.valid_until,
            draft=False,
            note=q.review_note,
        )
    )


def store_final_pdf(q: Quotation) -> None:
    """Called after approval is committed. If it fails, pdf_response regenerates on demand."""
    assert q.pdf_file
    try:
        save_pdf(q.pdf_file, render_final(q))
    except Exception:
        logger.exception("Could not store PDF for %s", q.number)


def pdf_response(q: Quotation, settings: PricingSettings) -> Response:
    if q.status == QuotationStatus.PENDING:
        data = render_quotation_pdf(
            PdfInput(
                snapshot=q.snapshot,
                business=business_snapshot(settings),
                reference=f"DRAFT-{str(q.id)[:8].upper()}",
                created_at=q.created_at,
                valid_until=None,
                draft=True,
            )
        )
        name = f"estimate-{str(q.id)[:8]}.pdf"
    elif q.status == QuotationStatus.APPROVED and q.pdf_file:
        data = read_pdf(q.pdf_file)
        if data is None:  # file lost or never written: rebuild from the frozen snapshot
            data = render_final(q)
            save_pdf(q.pdf_file, data)
        name = q.pdf_file
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "No PDF for this quotation")

    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{name}"',
            "Cache-Control": "private, no-store",
        },
    )
