from pydantic_settings import BaseSettings, SettingsConfigDict


class TestConfig(BaseSettings):
    database_url: str
    api_url: str
    redis_url: str

    model_config = SettingsConfigDict(extra="ignore")

    @classmethod
    def load_config(cls) -> "TestConfig":
        return cls()
