"""Core settings shared by every NOVAH app — DB, Redis, LLM, identity. (Substrate.)

App-specific knobs (channel creds, transcription provider, watched folders) live in each
app's own settings, NOT here. Keeping core config channel-agnostic lets one runtime serve
many apps. Requires pydantic-settings (novahos[substrate]).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://novah:novah@localhost:5432/novah"
    db_schema: str = "novah"
    redis_url: str = "redis://localhost:6379"

    reasoning_model: str = "claude-opus-4-8"
    cheap_model: str = "claude-haiku-4-5-20251001"

    owner_emails: str = ""
    account_header: str = "X-Leadfuel-Account"

    env: str = "dev"
    log_level: str = "info"

    @property
    def owner_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.owner_emails.split(",") if e.strip()}


settings = CoreSettings()
