import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    price_in_per_m: float
    price_out_per_m: float
    max_upload_bytes: int


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        price_in_per_m=float(os.getenv("LLM_PRICE_IN_PER_M", "0")),
        price_out_per_m=float(os.getenv("LLM_PRICE_OUT_PER_M", "0")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    )
