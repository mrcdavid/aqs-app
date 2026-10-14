from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import PersonName, PhMobile, PlaceName


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: PersonName
    age: int = Field(ge=18, le=120)
    contact_number: PhMobile
    address_line: str = Field(min_length=5, max_length=200)
    city: PlaceName
    province: PlaceName


class ProfileOut(BaseModel):
    """Plain types on purpose: profiles saved before a rule changed must still load."""

    model_config = ConfigDict(from_attributes=True)

    full_name: str
    age: int
    contact_number: str
    address_line: str
    city: str
    province: str
