from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str  # no default — must be set via env var
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    frontend_url: str = "http://localhost:5173"  # default to local dev frontend URL
    # frontend_url: str = "https://dgreneral-dashboard.netlify.app"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    allowed_email_domain: str = "gslaw.edu.gh"
    oauth_state_expire_minutes: int = 5
    exchange_code_expire_minutes: int = 2
    onboarding_token_expire_minutes: int = 10


settings = Settings()
