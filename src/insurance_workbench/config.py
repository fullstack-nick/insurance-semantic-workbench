"""Project-local settings. Credentials never travel to the assistant process."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ISW_", env_file=str(ROOT / ".env"), extra="ignore")
    db_password: str
    db_app_password: str = ""
    db_source_password: str = ""
    db_worker_password: str = ""
    db_reader_password: str = ""
    db_port: int = 54320
    at_port: int = 13030
    cz_port: int = 13031
    web_port: int = 8000
    namespace: str = Field(default="isw", pattern=r"^isw(?:-[a-z0-9-]+)?$")
    data_root: Path = ROOT / ".runtime"
    model_dir: Path = ROOT / ".runtime/models/multilingual-e5-small"
    codex_home: Path = Path.home() / ".isw-codex"
    codex_model: str | None = None
    agent_timeout: int = 180
    tool_timeout: int = 20
    tool_budget: int = 20

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username="isw",
            password=self.db_password,
            host="127.0.0.1",
            port=self.db_port,
            database="workbench",
        )

    def role_url(self, role: str) -> URL:
        if role == "migration":
            return self.database_url
        if role not in {"app", "source", "worker", "reader"}:
            raise ValueError("Unknown database role")
        password = getattr(self, f"db_{role}_password")
        if not password:
            raise ValueError("Database role credentials are missing; run Setup-Lab.ps1")
        return URL.create(
            "postgresql+psycopg",
            username="isw_" + role,
            password=password,
            host="127.0.0.1",
            port=self.db_port,
            database="workbench",
        )

    def endpoint(self, country: str) -> str:
        if country not in {"AT", "CZ"}:
            raise ValueError("Unknown country profile")
        return f"http://127.0.0.1:{self.at_port if country == 'AT' else self.cz_port}/ds"

    def prepare(self) -> None:
        self.data_root = self.data_root.resolve()
        for name in ["sources", "graphs", "reports", "backups", "logs"]:
            (self.data_root / name).mkdir(parents=True, exist_ok=True)


@lru_cache
def settings() -> Settings:
    result = Settings()
    result.prepare()
    return result
