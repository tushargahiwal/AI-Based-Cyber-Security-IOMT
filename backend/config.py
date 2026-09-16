from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "IoMT IDS Backend"
    env: str = "development"
    debug: bool = True

    database_url: str = "mysql+pymysql://root:@127.0.0.1:3306/iomt_ids?charset=utf8mb4"
    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883

    # Browser origins allowed to call this API. Needed as soon as the frontend
    # is served from a different host than the backend — a Vercel deployment
    # calling a backend elsewhere, for instance. Comma-separated.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Required to create the FIRST account with a privileged role. Without it,
    # "the users table is empty so this one becomes admin" is a race that
    # anyone who finds a public deployment can win. Leave empty in development
    # — the guard only binds when ENV is something else.
    bootstrap_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    # Retention. Detection and vitals volume grows without limit otherwise, and
    # keeping patient-linked telemetry longer than it is useful is exactly what
    # a data-protection review objects to. 0 disables pruning for that table.
    retention_detections_days: int = 90
    retention_vitals_days: int = 30
    retention_audit_days: int = 365


DEFAULT_JWT_SECRET = "change-me-to-a-random-secret"

settings = Settings()

# A deployment signing tokens with the published default is a deployment anyone
# can forge an admin token for. In development that is a convenience; anywhere
# else it is a hole, so the app refuses to start rather than run insecurely and
# look fine.
if settings.env != "development" and settings.jwt_secret_key == DEFAULT_JWT_SECRET:
    raise RuntimeError(
        f"JWT_SECRET_KEY is still the default while ENV={settings.env!r}. "
        "Set it to a random value (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`) "
        "before starting outside development."
    )
