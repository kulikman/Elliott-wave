"""Централизованная конфигурация проекта."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Корень проекта — два уровня вверх от tools/_lib/
ROOT = Path(__file__).parent.parent.parent

load_dotenv(ROOT / ".env", override=True)

# Директории
SCHEMAS_DIR   = ROOT / "schemas"
AKU_DIR       = ROOT / "aku"
GOLDEN_DIR    = AKU_DIR / "golden"
INBOX_DIR     = ROOT / "inbox"
RAW_VAULT_DIR = ROOT / "raw-vault"
EXTRACTED_DIR = ROOT / "extracted"
BRAIN_OUT_DIR = ROOT / "brain-output"
KB_DIR        = BRAIN_OUT_DIR / "kb"
SPEC_DIR      = BRAIN_OUT_DIR / "indicator-spec"
DOCS_DIR      = ROOT / "docs"
TOOLS_DIR     = ROOT / "tools"


def get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "sk-ant-...":
        raise EnvironmentError(
            "❌ ANTHROPIC_API_KEY не задан.\n"
            "   Скопируй .env.example → .env и заполни ключ."
        )
    return key


def get_api_key_optional() -> str | None:
    """Возвращает ключ или None — для инструментов которые работают без API."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key == "sk-ant-...":
        return None
    return key


EXTRACTION_MODEL   = os.getenv("EXTRACTION_MODEL", "claude-opus-4-6")
VISION_MODEL       = os.getenv("VISION_MODEL", "claude-opus-4-6")
FORMALIZATION_MODEL = os.getenv("FORMALIZATION_MODEL", "claude-opus-4-6")
MAX_AKU_PER_REQUEST = int(os.getenv("MAX_AKU_PER_REQUEST", "10"))
MAX_SECTION_WORDS   = int(os.getenv("MAX_SECTION_WORDS", "3000"))
