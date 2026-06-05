#!/usr/bin/env python3
"""
vision_pages.py — Vision-описание выбранных страниц PDF.

Запуск:
  python tools/vision_pages.py --book-id intraday-l03-s-curves --pages 33-36 --force
  python tools/vision_pages.py --book-id intraday-l08-fractal-dimension-shift --pages 30 --output vision-notes-page-030.md

Выход:
  extracted/{book_id}/vision-notes.md
"""

import argparse
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib import config
from tools._lib.anthropic_client import call_with_retry, get_client
from tools._lib.config import EXTRACTED_DIR
from tools._lib.log import error, info, ok, section, warn


SYSTEM_PROMPT = (
    "Ты анализируешь страницы русскоязычных материалов по волновому анализу. "
    "Нужно извлекать только то, что видно на изображении, без домыслов. "
    "Если подпись неразборчива, пиши 'неразборчиво'."
)


USER_PROMPT = """
Проанализируй эти страницы как источник для будущих AKU.

Для каждой страницы дай:
1. Краткое описание схемы/графика.
2. Все видимые подписи, числа, проценты, формулы и волновые метки дословно.
3. Что связано с Нили / Elliott / NeoWave, если это явно видно.
4. Возможные AKU-кандидаты:
   - definition
   - conditional_rule
   - heuristic
   - exception
5. Что требует human review.

Правила:
- Не выдумывай отсутствующий текст.
- Не превращай эвристику в обязательное правило.
- Если вывод зависит от картинки, пометь requires_review.
"""


def parse_pages(value: str) -> list[int]:
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    return sorted(dict.fromkeys(pages))


def image_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": data,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Vision-описание выбранных pdf-pages")
    parser.add_argument("--book-id", required=True)
    parser.add_argument("--pages", required=True, help="Например: 33-36 или 33,34,40")
    parser.add_argument(
        "--output",
        default="vision-notes.md",
        help="Имя файла внутри extracted/{book_id}; по умолчанию vision-notes.md",
    )
    parser.add_argument("--force", action="store_true", help="Перезаписать output-файл")
    args = parser.parse_args()

    if not config.get_api_key_optional():
        error("ANTHROPIC_API_KEY не задан")
        sys.exit(1)

    book_dir = EXTRACTED_DIR / args.book_id
    pages_dir = book_dir / "pdf-pages"
    if not pages_dir.exists():
        error(f"Нет pdf-pages: {pages_dir}")
        sys.exit(1)

    selected_pages = parse_pages(args.pages)
    image_paths = []
    for page in selected_pages:
        path = pages_dir / f"page-{page:03d}.png"
        if not path.exists():
            error(f"Страница не найдена: {path}")
            sys.exit(1)
        image_paths.append((page, path))

    out_path = book_dir / args.output
    if out_path.parent != book_dir:
        error("--output должен быть именем файла внутри директории книги")
        sys.exit(1)

    if out_path.exists() and not args.force:
        warn(f"Файл уже существует: {out_path}")
        warn("Используй --force чтобы перезаписать")
        sys.exit(0)

    section(f"Vision pages: {args.book_id}")
    info(f"Страницы: {', '.join(str(p) for p, _ in image_paths)}")

    content = []
    for page, path in image_paths:
        content.append({"type": "text", "text": f"Страница {page}:"})
        content.append(image_block(path))
    content.append({"type": "text", "text": USER_PROMPT})

    client = get_client()
    result = call_with_retry(
        client=client,
        model=config.VISION_MODEL,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        max_tokens=4096,
        temperature=0.0,
    )

    header = (
        f"# Vision notes — {args.book_id}\n\n"
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        f"- Pages: {', '.join(str(p) for p, _ in image_paths)}\n"
        f"- Model: {config.VISION_MODEL}\n\n"
    )
    out_path.write_text(header + result.strip() + "\n", encoding="utf-8")
    ok(f"Сохранено: {out_path}")


if __name__ == "__main__":
    main()
