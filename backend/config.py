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


settings = Settings()
