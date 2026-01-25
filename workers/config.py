import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_available() -> None:
    """Best-effort .env loading without hard dependency."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    # Prefer loading the workers/.env next to this file (works no matter the cwd)
    try:
        env_path = Path(__file__).resolve().parent / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
    except Exception:
        pass
    # Also try default resolution (cwd-based) as a fallback
    load_dotenv(override=False)


@dataclass(frozen=True)
class Config:
    # Database
    database_url: str
    database_max_connections: int = 10
    database_timeout_seconds: int = 30

    # Storage
    storage_base_path: str = "/shared"
    storage_uploads_dir: str = "uploads"
    storage_extracted_dir: str = "extracted"
    storage_temp_dir: str = "temp"
    storage_logs_dir: str = "logs"

    # Processing
    max_retry_attempts: int = 3
    retry_base_delay_seconds: float = 2.0
    retry_max_delay_seconds: float = 60.0
    batch_processing_timeout_seconds: int = 1800

    # LLM (Phase 4)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4096
    openai_rate_limit_rpm: int = 60

    # OCR configuration
    enable_ocr: bool = True
    ocr_max_pages: int = 50
    
    # GAEB configuration
    gaeb_enabled: bool = True

    # Redis Queue
    redis_url: str = "redis://localhost:6379"
    redis_queue_key: str = "tender:jobs"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file_path: str = "/shared/logs/worker.log"

    # Redis queue
    redis_url: str = "redis://localhost:6379"
    redis_queue_key: str = "tender:jobs"

    def validate(self) -> None:
        if not (
            self.database_url.startswith("postgresql://")
            or self.database_url.startswith("postgresql+psycopg://")
            or self.database_url.startswith("postgresql+psycopg2://")
        ):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql://', 'postgresql+psycopg://', or 'postgresql+psycopg2://'"
            )

        if self.database_max_connections < 1 or self.database_max_connections > 50:
            raise ValueError("DATABASE_MAX_CONNECTIONS must be between 1 and 50")

        if self.database_timeout_seconds < 1 or self.database_timeout_seconds > 120:
            raise ValueError("DATABASE_TIMEOUT must be between 1 and 120 seconds")

        if self.max_retry_attempts < 0 or self.max_retry_attempts > 10:
            raise ValueError("MAX_RETRY_ATTEMPTS must be between 0 and 10")

        if self.retry_base_delay_seconds <= 0:
            raise ValueError("RETRY_BASE_DELAY_SECONDS must be > 0")

        if self.retry_max_delay_seconds < self.retry_base_delay_seconds:
            raise ValueError("RETRY_MAX_DELAY_SECONDS must be >= RETRY_BASE_DELAY_SECONDS")

        if self.batch_processing_timeout_seconds < 60:
            raise ValueError("BATCH_PROCESSING_TIMEOUT must be >= 60 seconds")

        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

        if self.log_format not in {"json", "text"}:
            raise ValueError("LOG_FORMAT must be 'json' or 'text'")

        base_path = Path(self.storage_base_path)
        if not base_path.exists():
            raise ValueError(f"STORAGE_BASE_PATH does not exist: {self.storage_base_path}")
        if not os.access(base_path, os.W_OK):
            raise ValueError(f"STORAGE_BASE_PATH is not writable: {self.storage_base_path}")

    def get_storage_path(self, subdir: str) -> str:
        return str(Path(self.storage_base_path) / subdir)

    def get_uploads_path(self) -> str:
        return self.get_storage_path(self.storage_uploads_dir)

    def get_extracted_path(self) -> str:
        return self.get_storage_path(self.storage_extracted_dir)

    def get_temp_path(self) -> str:
        return self.get_storage_path(self.storage_temp_dir)

    def get_logs_path(self) -> str:
        return self.get_storage_path(self.storage_logs_dir)


def load_config() -> Config:
    _load_dotenv_if_available()

    config = Config(
        database_url=os.environ.get("DATABASE_URL", "").strip(),
        database_max_connections=int(os.environ.get("DATABASE_MAX_CONNECTIONS", "10")),
        database_timeout_seconds=int(os.environ.get("DATABASE_TIMEOUT", "30")),
        storage_base_path=os.environ.get("STORAGE_BASE_PATH", "/shared"),
        storage_uploads_dir=os.environ.get("STORAGE_UPLOADS_DIR", "uploads"),
        storage_extracted_dir=os.environ.get("STORAGE_EXTRACTED_DIR", "extracted"),
        storage_temp_dir=os.environ.get("STORAGE_TEMP_DIR", "temp"),
        storage_logs_dir=os.environ.get("STORAGE_LOGS_DIR", "logs"),
        max_retry_attempts=int(os.environ.get("MAX_RETRY_ATTEMPTS", "3")),
        retry_base_delay_seconds=float(os.environ.get("RETRY_BASE_DELAY_SECONDS", "2.0")),
        retry_max_delay_seconds=float(os.environ.get("RETRY_MAX_DELAY_SECONDS", "60.0")),
        batch_processing_timeout_seconds=int(os.environ.get("BATCH_PROCESSING_TIMEOUT", "1800")),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        openai_max_tokens=int(os.environ.get("OPENAI_MAX_TOKENS", "4096")),
        openai_rate_limit_rpm=int(os.environ.get("OPENAI_RATE_LIMIT_RPM", "60")),
        enable_ocr=os.environ.get("ENABLE_OCR", "true").lower() in ("true", "1", "yes"),
        ocr_max_pages=int(os.environ.get("OCR_MAX_PAGES", "50")),
        gaeb_enabled=os.environ.get("GAEB_ENABLED", "true").lower() in ("true", "1", "yes"),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
        redis_queue_key=os.environ.get("REDIS_QUEUE_KEY", "tender:jobs"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        log_format=os.environ.get("LOG_FORMAT", "json"),
        log_file_path=os.environ.get("LOG_FILE_PATH", "/shared/logs/worker.log"),
    )

    config.validate()
    return config
