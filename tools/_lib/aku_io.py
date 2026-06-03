"""Чтение и запись AKU YAML с базовой валидацией структуры."""

import re
import yaml
from pathlib import Path
from datetime import datetime, timezone

from tools._lib.config import AKU_DIR, SCHEMAS_DIR
from tools._lib.log import warn

AKU_ID_PATTERN = re.compile(r"^AKU-(\d{4})$")


def load_aku(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"AKU файл не является YAML словарём: {path}")
    return data


def save_aku(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def next_aku_id() -> str:
    existing: set[int] = set()
    for yaml_file in AKU_DIR.rglob("*.yaml"):
        try:
            data = load_aku(yaml_file)
            m = AKU_ID_PATTERN.match(str(data.get("id", "")))
            if m:
                existing.add(int(m.group(1)))
        except Exception:
            pass
    num = max(existing) + 1 if existing else 1
    return f"AKU-{num:04d}"


def load_all_aku(status_filter: str | None = None) -> list[dict]:
    """Загружает все AKU из базы, опционально фильтруя по статусу."""
    result = []
    for yaml_file in sorted(AKU_DIR.rglob("*.yaml")):
        try:
            data = load_aku(yaml_file)
            if "id" not in data:
                continue
            if status_filter and data.get("status") != status_filter:
                continue
            data["_filepath"] = yaml_file
            result.append(data)
        except Exception as e:
            warn(f"Не удалось загрузить {yaml_file.name}: {e}")
    return result


def load_golden_examples(pass_type: str | None = None, limit: int = 2) -> list[dict]:
    """Загружает golden AKU как примеры для промптов."""
    examples = []
    for yaml_file in sorted((AKU_DIR / "golden").glob("*.yaml")):
        try:
            data = load_aku(yaml_file)
            examples.append(data)
            if len(examples) >= limit:
                break
        except Exception:
            pass
    return examples


def parse_yaml_from_llm_response(text: str) -> list[dict]:
    """
    Парсит YAML список AKU из ответа LLM.
    LLM может вернуть: чистый YAML, YAML в ```yaml блоке, или смешанный текст.
    """
    original = text

    # Убираем все фенс-блоки (```yaml ... ``` или ``` ... ```)
    # Сначала пробуем извлечь содержимое из первого фенс-блока
    fence_match = re.search(r"```(?:yaml)?[ \t]*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # Убираем оставшиеся ``` без закрывающего тега
        text = re.sub(r"^```(?:yaml)?[ \t]*$", "", text, flags=re.MULTILINE).strip()
        text = re.sub(r"^```[ \t]*$", "", text, flags=re.MULTILINE).strip()

    # Если пустой список — вернуть []
    if text.strip() in ("[]", "- []", ""):
        return []

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"Невалидный YAML в ответе LLM: {e}\n\nТекст:\n{text[:500]}")

    if parsed is None:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    raise ValueError(f"Ответ LLM не является YAML словарём или списком: {type(parsed)}")


def aku_path(book_id: str, chapter_num: int, chapter_slug: str, aku_id: str) -> Path:
    folder = AKU_DIR / book_id / f"ch{chapter_num:02d}-{chapter_slug}"
    return folder / f"{aku_id}.yaml"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
