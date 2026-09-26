from pydantic import BaseModel, ConfigDict, Field

# Philippine mobile number: 09XXXXXXXXX or +639XXXXXXXXX
PH_MOBILE_PATTERN = r"^(09|\+639)\d{9}$"


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=18, le=120)
    contact_number: str = Field(pattern=PH_MOBILE_PATTERN, max_length=20)
    address_line: str = Field(min_length=5, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    province: str = Field(min_length=2, max_length=80)


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)
