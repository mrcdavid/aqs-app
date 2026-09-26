"""App settings, loaded from environment variables / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AQS APP"
    environment: str = Field(default="development", pattern="^(development|test|production)$")

    # Where the browser loads the app from. Used for the CSRF Origin check and OAuth redirects.
    app_origin: str = "http://localhost:5173"

    # Runtime DB connection (least-privilege role).
    database_url: SecretStr
    # Superuser connection, used only by scripts/create_db.py.
    postgres_admin_url: SecretStr | None = None

    # Secret for signing the short-lived OAuth state cookie.
    secret_key: SecretStr

    # Google OAuth (customers)
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    allowed_email_domain: str = "up.edu.ph"

    # Sessions
    csrf_cookie_name: str = "aqs_csrf"
    oauth_state_cookie_name: str = "aqs_oauth"
    user_idle_minutes: int = 8 * 60
    staff_idle_minutes: int = 30
    session_absolute_days: int = 7

    # Quotations
    quote_storage_dir: Path = Path("storage/quotes")  # final PDFs; relative to backend/
    max_pending_quotations: int = 20  # per customer, to limit spam

    # Staff login protection
    max_failed_logins: int = 10
    lockout_minutes: int = 15

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production

    @property
    def session_cookie_name(self) -> str:
        # `__Host-` requires the Secure flag, which needs HTTPS; plain name in local dev/tests.
        return "__Host-aqs_session" if self.secure_cookies else "aqs_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
