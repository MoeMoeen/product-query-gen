import os
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
from typing import Optional, Any

try:
    # OpenAI SDK v1+ provides AsyncOpenAI
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover - fallback if package not available at import time
    AsyncOpenAI = None  # type: ignore


# Load .env file if present
load_dotenv()

class Settings(BaseModel):
    project_name: str = "Product Query Generator"
    version: str = "0.1.0"

    # LLM
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "400"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()



def setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    return logging.getLogger("query-gen")


def get_openai_async_client() -> Optional[Any]:
    """Create and return an AsyncOpenAI client using env-configured API key.

    Returns None if the OpenAI SDK isn't available. Callers should handle that case.
    """
    if AsyncOpenAI is None:
        return None
    api_key = settings.openai_api_key
    # Allow instantiation even if key is empty; downstream can error explicitly
    return AsyncOpenAI(api_key=api_key)
