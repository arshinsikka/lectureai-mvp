from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    openai_api_key: str = ""
    google_api_key: str = ""

    # Email
    smtp_email: str = ""
    smtp_password: str = ""
    recipient_email: str = ""

    # Paths
    data_dir: Path = Path("data")
    outputs_dir: Path = Path("outputs")

    # Models
    whisper_model: str = "whisper-1"
    llm_model: str = "gpt-4o"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def session_data_dir(self, session_id: str) -> Path:
        path = self.data_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def session_outputs_dir(self, session_id: str) -> Path:
        path = self.outputs_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    return Settings()
