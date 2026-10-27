from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://plantmitra:plantmitra@localhost:5432/plantmitra"
    jwt_secret: str
    jwt_expire_minutes: int = 10080
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:3000"
    plantnet_api_key: str = ""
    plantmitra_ml_python: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
