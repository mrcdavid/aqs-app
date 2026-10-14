"""Field types with input rules shared by several request schemas.

Used by the customer profile, walk-in clients (typed in by staff) and pricing settings, so the
same rules apply everywhere. Mirrored for fast feedback in frontend/src/lib/schemas.ts.
"""

import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, Field
from pydantic_core import PydanticCustomError

# Philippine mobile number, stored without spaces: 09XXXXXXXXX or +639XXXXXXXXX.
PH_MOBILE_PATTERN = r"^(09|\+639)\d{9}$"
_PHONE_SEPARATORS = re.compile(r"[\s().-]")

_NAME_EXTRA = frozenset(" .,'’-")  # Ma. Cristina O'Neil-Reyes, Jr.
_PLACE_EXTRA = _NAME_EXTRA | {"(", ")"}  # Science City of Muñoz, Cotabato (North)


def _ph_mobile(value: str) -> str:
    """Accept what people type ("0917 123 4567", "+63 917-123-4567"), store digits only."""
    value = _PHONE_SEPARATORS.sub("", value)
    if not re.fullmatch(PH_MOBILE_PATTERN, value):
        raise PydanticCustomError(
            "ph_mobile",
            "must be a Philippine mobile number, e.g. 0917 123 4567 or +63 917 123 4567",
        )
    return value


def _letters(value: str, extra: frozenset[str]) -> str:
    value = " ".join(value.split())  # collapse repeated spaces
    if value and not (value[0].isalpha() and all(c.isalpha() or c in extra for c in value)):
        raise PydanticCustomError("letters", "use letters only (spaces and . , ' - are fine)")
    return value


def _person_name(value: str) -> str:
    return _letters(value, _NAME_EXTRA)


def _place_name(value: str) -> str:
    return _letters(value, _PLACE_EXTRA)


def _blank_to_none(value: object) -> object:
    return None if isinstance(value, str) and not value.strip() else value


PhMobile = Annotated[str, Field(max_length=20), AfterValidator(_ph_mobile)]
PersonName = Annotated[str, Field(min_length=2, max_length=120), AfterValidator(_person_name)]
# Same rule, but may be left empty.
OptionalPersonName = Annotated[str, Field(max_length=120), AfterValidator(_person_name)]
PlaceName = Annotated[str, Field(min_length=2, max_length=80), AfterValidator(_place_name)]
# Optional email: blank means "none"; anything else must be a valid address.
OptionalEmail = Annotated[EmailStr | None, BeforeValidator(_blank_to_none)]
