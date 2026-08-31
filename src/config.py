from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/face_auth"
    face_match_threshold: float = 0.5
    insightface_model_name: str = "buffalo_l"


settings = Settings()
