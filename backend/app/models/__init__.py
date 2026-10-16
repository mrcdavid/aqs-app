"""Import every model module here so Alembic autogenerate can see it."""

from app.models.audit import AuditLog
from app.models.catalog import (
    Basis,
    LaborRate,
    Material,
    MaterialCategory,
    PriceUnit,
    PricingSettings,
    Product,
    ProductCategory,
    ProductComponent,
    ProductOption,
    ProductOptionGroup,
)
from app.models.quotation import (
    MAX_ITEMS,
    Quotation,
    QuotationItem,
    QuotationStatus,
    QuoteCounter,
)
from app.models.session import AuthSession
from app.models.user import AuthProvider, Profile, Role, User

__all__ = [
    "AuditLog",
    "AuthProvider",
    "AuthSession",
    "Basis",
    "LaborRate",
    "Material",
    "MaterialCategory",
    "PriceUnit",
    "PricingSettings",
    "Product",
    "ProductCategory",
    "ProductComponent",
    "ProductOption",
    "ProductOptionGroup",
    "Profile",
    "MAX_ITEMS",
    "Quotation",
    "QuotationItem",
    "QuotationStatus",
    "QuoteCounter",
    "Role",
    "User",
]
