from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://omni:omnipass@localhost:5432/omni_db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_env: str = "development"
    allowed_origins: str = "chrome-extension://,http://localhost:3000"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
