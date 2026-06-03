#!/usr/bin/env python3
"""
ingest.py — MarkItDown pipeline: книга → structured markdown

Запуск:
  python tools/ingest.py <path> --book-id <id> [--part <1|2|3>] [--force]

Примеры:
  python tools/ingest.py inbox/neely.doc --book-id neely-mwe-1990
  python tools/ingest.py inbox/neely_1.pdf --book-id neely-mwe-1990 --part 1
  python tools/ingest.py inbox/neely_3.pdf --book-id neely-mwe-1990 --part 3 --force
"""

import argparse
import hashlib
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Позволяет запускать как `python tools/ingest.py` из корня проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib import config
from tools._lib.log import info, ok, warn, error, step, section
from tools._lib.config import EXTRACTED_DIR, INBOX_DIR, SCHEMAS_DIR

import yaml


# ── Helpers ──────────────────────────────────────────────────────────────────

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_existing_metadata(out_dir: Path) -> dict | None:
    meta_path = out_dir / "metadata.yaml"
    if not meta_path.exists():
        return None
    with open(meta_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_metadata(out_dir: Path, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "metadata.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, sort_keys=False)


def word_count(text: str) -> int:
    return len(text.split())


# ── Ingestion: DOC ────────────────────────────────────────────────────────────

def ingest_doc(path: Path) -> str:
    """
    Конвертирует DOC/DOCX в markdown.
    .docx → MarkItDown
    старый бинарный .doc → antiword (требует: brew install antiword)
    """
    suffix = path.suffix.lower()

    if suffix == ".docx":
        try:
            from markitdown import MarkItDown
        except ImportError:
            raise ImportError("❌ pip install markitdown")
        info(f"Конвертирую DOCX: {path.name}")
        md = MarkItDown()
        result = md.convert(str(path))
        text = result.text_content
    else:
        # Старый бинарный .doc — используем antiword
        import subprocess, shutil
        if not shutil.which("antiword"):
            raise RuntimeError(
                "❌ antiword не установлен.\n"
                "   Запусти: brew install antiword"
            )
        info(f"Конвертирую DOC через antiword: {path.name}")
        result = subprocess.run(
            ["antiword", "-m", "UTF-8.txt", "-w", "0", str(path)],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"antiword завершился с ошибкой: {result.stderr.decode('utf-8', errors='replace')}"
            )
        text = result.stdout.decode("utf-8", errors="replace")

    if not text or not text.strip():
        raise ValueError(f"Конвертер вернул пустой текст для {path.name}")
    info(f"Извлечено {len(text):,} символов, ~{word_count(text):,} слов")
    return text


# ── Ingestion: PDF ────────────────────────────────────────────────────────────

def ingest_pdf_clean(path: Path) -> str:
    """PDF без значимых изображений — через MarkItDown напрямую."""
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError("❌ MarkItDown не установлен. pip install markitdown[all]")

    info(f"Конвертирую PDF (text mode): {path.name}")
    md = MarkItDown()
    result = md.convert(str(path))
    text = result.text_content
    if not text or not text.strip():
        raise ValueError(f"MarkItDown вернул пустой текст для {path.name}")
    info(f"Извлечено {len(text):,} символов, ~{word_count(text):,} слов")
    return text


VISION_PROMPT = (
    "Это страница из книги по волновому анализу Эллиотта (метод Нили/NeoWave).\n"
    "Задача: извлечь весь текст и описать все диаграммы.\n\n"
    "ПРАВИЛА:\n"
    "1. Весь текст — дословно, сохраняя абзацы\n"
    "2. Нумерованные и маркированные списки — сохранять структуру\n"
    "3. Таблицы — воспроизводить в markdown\n"
    "4. Если есть волновая разметка/диаграмма:\n"
    "   - Опиши обозначенные волны (1,2,3,4,5 / A,B,C)\n"
    "   - Укажи направление (вверх/вниз)\n"
    "   - Воспроизведи все подписи, числа, проценты дословно\n"
    "   - Структурные обозначения: :3, :5, :F3, :L3 и т.д.\n"
    "5. Блок-схемы — все узлы и стрелки\n"
    "Выводи в формате: текст страницы N, затем [ДИАГРАММА N: описание] если есть диаграмма."
)


def ingest_pdf_with_ocr(path: Path, pages_per_batch: int = 3) -> str:
    """
    PDF сканированный — постраничный OCR через Anthropic Vision.
    Обрабатывает батчами по pages_per_batch страниц для снижения числа API вызовов.
    """
    api_key = config.get_api_key_optional()
    if not api_key:
        warn("ANTHROPIC_API_KEY не задан — Vision OCR недоступен")
        raise RuntimeError(
            "❌ Для OCR сканированного PDF нужен ANTHROPIC_API_KEY в .env"
        )

    try:
        import fitz  # PyMuPDF
        import anthropic as _anthropic
        import base64
    except ImportError as e:
        raise ImportError(
            f"❌ Недостаёт зависимости: {e}\n"
            "   pip install pymupdf anthropic"
        )

    info(f"Конвертирую сканированный PDF через Vision OCR: {path.name}")

    doc = fitz.open(str(path))
    total_pages = len(doc)
    info(f"Страниц: {total_pages} | Батчей (~{pages_per_batch} стр/батч): {(total_pages + pages_per_batch - 1) // pages_per_batch}")

    client = _anthropic.Anthropic(api_key=api_key)
    all_text_parts = []

    for batch_start in range(0, total_pages, pages_per_batch):
        batch_end = min(batch_start + pages_per_batch, total_pages)
        batch_pages = list(range(batch_start, batch_end))

        # Рендерим страницы в PNG (150 DPI — баланс качество/размер)
        content_blocks = []
        for page_num in batch_pages:
            page = doc[page_num]
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img_b64 = base64.standard_b64encode(img_bytes).decode()

            content_blocks.append({
                "type": "text",
                "text": f"Страница {page_num + 1}:"
            })
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_b64,
                }
            })

        content_blocks.append({
            "type": "text",
            "text": VISION_PROMPT
        })

        from tools._lib.anthropic_client import call_with_retry
        batch_text = call_with_retry(
            client=client,
            model=config.VISION_MODEL,
            messages=[{"role": "user", "content": content_blocks}],
            max_tokens=4096,
            temperature=0.0,
        )

        all_text_parts.append(batch_text)

        pages_done = batch_end
        from tools._lib.log import progress
        progress(pages_done, total_pages, f"стр. {pages_done}/{total_pages}")

    doc.close()
    print()  # newline после progress bar

    result = "\n\n".join(all_text_parts)
    info(f"Извлечено {len(result):,} символов, ~{word_count(result):,} слов (Vision OCR)")
    return result


# ── Merge PDF parts ───────────────────────────────────────────────────────────

def merge_parts(out_dir: Path) -> str:
    """Объединяет part_1.md, part_2.md, part_3.md в один full-text.md."""
    parts = []
    for i in range(1, 10):
        p = out_dir / f"part_{i}.md"
        if p.exists():
            parts.append((i, p))

    if not parts:
        raise FileNotFoundError(f"Нет частей для объединения в {out_dir}")

    chunks = []
    for idx, p in sorted(parts):
        chunks.append(f"\n\n<!-- PART {idx} -->\n\n")
        with open(p, "r", encoding="utf-8") as f:
            chunks.append(f.read())

    merged = "".join(chunks).strip()
    info(f"Объединено {len(parts)} частей → {len(merged):,} символов")
    return merged


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Конвертирует книгу (DOC/PDF) в markdown для Elliott Wave Brain"
    )
    parser.add_argument("path", help="Путь к файлу (DOC, DOCX, PDF, PNG)")
    parser.add_argument("--book-id", required=True, help="ID книги из books.yaml (пример: neely-mwe-1990)")
    parser.add_argument("--part", type=int, choices=[1, 2, 3, 4, 5], default=None,
                        help="Номер части PDF (если книга разбита на части)")
    parser.add_argument("--force", action="store_true",
                        help="Перезаписать даже если файл уже обработан")
    parser.add_argument("--no-ocr", action="store_true",
                        help="Не использовать OCR/Vision даже для PDF с картинками")
    args = parser.parse_args()

    # ── Проверка входного файла ───────────────────────────────────────────────
    src = Path(args.path)
    if not src.exists():
        error(f"Файл не найден: {src}")
        error("Убедись что путь правильный, или скопируй файл в inbox/")
        sys.exit(1)

    suffix = src.suffix.lower()
    if suffix not in {".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}:
        error(f"Неподдерживаемый формат: {suffix}")
        error("Поддерживаются: .doc, .docx, .pdf, .png, .jpg")
        sys.exit(1)

    # ── Проверка book_id ──────────────────────────────────────────────────────
    books_path = SCHEMAS_DIR / "books.yaml"
    with open(books_path, "r", encoding="utf-8") as f:
        books_data = yaml.safe_load(f)
    known_ids = {b["id"] for b in books_data.get("books", [])}
    if args.book_id not in known_ids:
        error(f"book_id '{args.book_id}' не найден в schemas/books.yaml")
        error(f"Доступные: {', '.join(sorted(known_ids))}")
        sys.exit(1)

    out_dir = EXTRACTED_DIR / args.book_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Проверка на повторную обработку ──────────────────────────────────────
    file_sha = sha256_of(src)
    existing_meta = load_existing_metadata(out_dir)

    if not args.part:
        # Основной файл → full-text.md
        out_md = out_dir / "full-text.md"
    else:
        out_md = out_dir / f"part_{args.part}.md"

    if out_md.exists() and not args.force:
        # Проверяем sha256 в метаданных
        already_done = False
        if existing_meta:
            for sf in existing_meta.get("source_files", []):
                if sf.get("sha256") == file_sha:
                    already_done = True
                    break

        if already_done:
            warn(f"Файл уже обработан (sha256 совпадает): {src.name}")
            warn("Используй --force чтобы перезаписать")
            sys.exit(0)

    # ── Extraction ────────────────────────────────────────────────────────────
    section(f"Ingestion: {src.name}")
    info(f"Книга: {args.book_id}")
    if args.part:
        info(f"Часть: {args.part}")

    if suffix in {".doc", ".docx"}:
        text = ingest_doc(src)

    elif suffix == ".pdf":
        if args.no_ocr:
            text = ingest_pdf_clean(src)
        else:
            # PDF части книги Нили содержат диаграммы → Vision
            text = ingest_pdf_with_ocr(src)

    else:
        # PNG/JPG — Vision напрямую
        text = ingest_pdf_with_ocr(src)

    # ── Сохранение ────────────────────────────────────────────────────────────
    step("Сохраняю результат")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write(text)

    ok(f"Сохранено: {out_md.relative_to(out_md.parent.parent.parent)}")
    info(f"Размер: {len(text):,} символов, ~{word_count(text):,} слов")

    # ── Если это была часть PDF — пробуем объединить ─────────────────────────
    if args.part:
        step("Проверяю наличие всех частей для объединения...")
        existing_parts = list(out_dir.glob("part_*.md"))
        info(f"Доступно частей: {len(existing_parts)}")

        full_text_path = out_dir / "full-text.md"
        if len(existing_parts) >= 1:
            info("Объединяю доступные части в full-text.md")
            merged = merge_parts(out_dir)
            with open(full_text_path, "w", encoding="utf-8") as f:
                f.write(merged)
            ok(f"full-text.md обновлён: {len(merged):,} символов")

    # ── Обновление метаданных ─────────────────────────────────────────────────
    meta = existing_meta or {
        "book_id": args.book_id,
        "ingested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ingest_version": "1.0",
        "source_files": [],
    }
    meta["ingested_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Обновляем или добавляем запись об этом файле
    src_entry = {
        "filename": src.name,
        "sha256": file_sha,
        "extracted_chars": len(text),
        "word_count": word_count(text),
        "part": args.part,
        "format": suffix.lstrip("."),
    }
    # Заменяем если уже есть запись для этого файла
    meta["source_files"] = [
        sf for sf in meta["source_files"]
        if sf.get("filename") != src.name
    ]
    meta["source_files"].append(src_entry)

    save_metadata(out_dir, meta)
    ok(f"metadata.yaml обновлён")

    section("Готово")
    ok(f"Книга '{args.book_id}' обработана.")
    info(f"Следующий шаг: python tools/chapter_map.py --book-id {args.book_id}")


if __name__ == "__main__":
    main()
