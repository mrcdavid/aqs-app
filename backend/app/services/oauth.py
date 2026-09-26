"""Google OpenID Connect client and the checks we apply to every Google identity."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

_settings = get_settings()

oauth = OAuth()
oauth.register(
    name="google",
    client_id=_settings.google_client_id,
    client_secret=_settings.google_client_secret.get_secret_value(),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
)


class GoogleIdentityError(Exception):
    """The Google account is valid but not allowed to use this app."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str


def verify_google_identity(claims: Mapping[str, Any], allowed_domain: str) -> GoogleIdentity:
    """Checks claims from a signature-verified ID token (Authlib validates iss/aud/exp/nonce).

    The `hd` login hint only pre-selects the account in Google's UI; it is not a security
    check. The domain must be verified here, from the token.
    """
    sub = claims.get("sub")
    email = str(claims.get("email") or "").strip().lower()
    if not sub or not email:
        raise GoogleIdentityError("missing_claims")
    if claims.get("email_verified") is not True:
        raise GoogleIdentityError("email_not_verified")
    domain = allowed_domain.lower()
    if claims.get("hd") != domain or not email.endswith("@" + domain):
        raise GoogleIdentityError("domain_not_allowed")
    return GoogleIdentity(sub=str(sub), email=email)
