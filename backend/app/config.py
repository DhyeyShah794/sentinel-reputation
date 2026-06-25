"""
Application configuration — environment-based settings.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root (Eminence/.env, one level above backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class Settings:
    """Central configuration for the Sentinel pipeline and API."""

    # --- Paths ---
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    DATA_RAW_DIR: Path = field(init=False)
    DATA_PROCESSED_DIR: Path = field(init=False)
    DATA_OUTPUTS_DIR: Path = field(init=False)

    # --- Dataset ---
    DATASET_FILENAME: str = "Dataset.xlsx"
    DATASET_SHEET_NAME: str = "ICICI Prudential AMC"
    BRAND_NAME: str = "ICICI Prudential AMC"
    BRAND_ALIASES: tuple = (
        "ICICI Prudential Mutual Fund",
        "ICICI Prudential AMC",
        "ICICI Pru",
        "iPru",
        "ICICI MF",
    )

    # --- LLM Provider (provider-agnostic) ---
    # Which backend to use: "ollama" | "gemini" | "openai"
    LLM_PROVIDER: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama")
    )

    # --- Ollama ---
    OLLAMA_BASE_URL: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    # Default model for all stages except those with a dedicated override below.
    OLLAMA_MODEL: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen3.6:35b-a3b-nvfp4")
    )
    # Per-stage model overrides — if empty, OLLAMA_MODEL is used.
    OLLAMA_MODEL_CLASSIFY: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_CLASSIFY", "")
    )
    OLLAMA_MODEL_SENTIMENT: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_SENTIMENT", "")
    )
    OLLAMA_MODEL_RELEVANCE: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_RELEVANCE", "")
    )
    OLLAMA_MODEL_RISK: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_RISK", "")
    )
    OLLAMA_MODEL_THEMES: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_THEMES", "")
    )
    # Executive summary uses a larger model by default.
    OLLAMA_MODEL_SUMMARY: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL_SUMMARY", "gemma4:latest")
    )
    OLLAMA_TIMEOUT: int = field(
        default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "300"))
    )
    OLLAMA_NUM_CTX: int = field(
        default_factory=lambda: int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    )
    OLLAMA_NUM_PREDICT: int = field(
        default_factory=lambda: int(os.getenv("OLLAMA_NUM_PREDICT", "8192"))
    )

    # --- Gemini ---
    GEMINI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    GEMINI_FLASH_MODEL: str = "gemini-2.0-flash"
    GEMINI_PRO_MODEL: str = "gemini-2.5-flash"

    # --- OpenAI ---
    OPENAI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    OPENAI_BASE_URL: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )

    # --- Embedding ---
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # --- Deduplication Thresholds ---
    FUZZY_DEDUP_THRESHOLD: float = 0.85
    SEMANTIC_DEDUP_THRESHOLD: float = 0.92

    # --- Relevance ---
    RELEVANCE_THRESHOLD: float = 0.3

    # --- Classification ---
    CLASSIFICATION_HIGH_CONFIDENCE: float = 0.75
    CLASSIFICATION_CONFIDENCE_GAP: float = 0.10

    # --- LLM batching (Batch API avoids realtime rate limits) ---
    LLM_BATCH_SIZE: int = 50
    LLM_BATCH_POLL_SECONDS: float = 5.0
    LLM_BATCH_CHUNK_DELAY_SECONDS: float = 10.0

    # --- API ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ])

    # --- Database (future) ---
    DATABASE_URL: Optional[str] = field(
        default_factory=lambda: os.getenv("DATABASE_URL")
    )

    def model_for_stage(self, stage: str) -> Optional[str]:
        """
        Return the model override for a pipeline stage, or None to use the provider default.

        Stage names: classify | sentiment | relevance | risk | themes | summary
        """
        _stage_map = {
            "classify": self.OLLAMA_MODEL_CLASSIFY,
            "classification": self.OLLAMA_MODEL_CLASSIFY,
            "sentiment": self.OLLAMA_MODEL_SENTIMENT,
            "relevance": self.OLLAMA_MODEL_RELEVANCE,
            "risk": self.OLLAMA_MODEL_RISK,
            "themes": self.OLLAMA_MODEL_THEMES,
            "summary": self.OLLAMA_MODEL_SUMMARY,
            "executive_summary": self.OLLAMA_MODEL_SUMMARY,
        }
        override = _stage_map.get(stage.lower(), "")
        return override if override else None

    def __post_init__(self):
        self.DATA_RAW_DIR = self.BASE_DIR / "data" / "raw"
        self.DATA_PROCESSED_DIR = self.BASE_DIR / "data" / "processed"
        self.DATA_OUTPUTS_DIR = self.BASE_DIR / "data" / "outputs"
        self.DATA_CACHE_DIR = self.BASE_DIR / "data" / "cache"
        self.LLM_CACHE_FILE = self.DATA_CACHE_DIR / "llm_cache.json"

        # Ensure directories exist
        self.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Singleton
settings = Settings()
