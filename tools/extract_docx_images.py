#!/usr/bin/env python3
"""
extract_docx_images.py — извлекает встроенные изображения из DOCX.

Запуск:
  python tools/extract_docx_images.py <path.docx> --book-id <id> [--force]

Выход:
  extracted/{book_id}/images/
  extracted/{book_id}/images-manifest.yaml
"""

import argparse
import hashlib
import mimetypes
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools._lib.config import EXTRACTED_DIR, SCHEMAS_DIR
from tools._lib.log import error, info, ok, section, step, warn


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_book_ids() -> set[str]:
    with open(SCHEMAS_DIR / "books.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {book["id"] for book in data.get("books", [])}


def read_relationships(zf: zipfile.ZipFile) -> dict[str, str]:
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in zf.namelist():
        return {}

    root = ET.fromstring(zf.read(rels_path))
    rels: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target", "")
        if rel_id and target.startswith("media/"):
            rels[rel_id] = f"word/{target}"
    return rels


def ordered_media_paths(zf: zipfile.ZipFile) -> list[str]:
    rels = read_relationships(zf)
    if "word/document.xml" not in zf.namelist():
        return sorted(name for name in zf.namelist() if name.startswith("word/media/"))

    root = ET.fromstring(zf.read("word/document.xml"))
    ordered: list[str] = []
    for blip in root.findall(".//a:blip", NS):
        rel_id = blip.attrib.get(f"{{{NS['r']}}}embed")
        media_path = rels.get(rel_id or "")
        if media_path:
            ordered.append(media_path)

    if ordered:
        return ordered
    return sorted(name for name in zf.namelist() if name.startswith("word/media/"))


def image_size(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
        import io

        with Image.open(io.BytesIO(data)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Извлекает картинки из DOCX")
    parser.add_argument("path", help="Путь к DOCX")
    parser.add_argument("--book-id", required=True, help="ID книги из books.yaml")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие картинки")
    args = parser.parse_args()

    src = Path(args.path)
    if not src.exists():
        error(f"Файл не найден: {src}")
        sys.exit(1)
    if src.suffix.lower() != ".docx":
        error("Поддерживается только .docx")
        sys.exit(1)
    if args.book_id not in load_book_ids():
        error(f"book_id '{args.book_id}' не найден в schemas/books.yaml")
        sys.exit(1)

    out_dir = EXTRACTED_DIR / args.book_id
    images_dir = out_dir / "images"
    manifest_path = out_dir / "images-manifest.yaml"

    if manifest_path.exists() and not args.force:
        warn(f"images-manifest.yaml уже существует: {manifest_path}")
        warn("Используй --force чтобы перезаписать")
        sys.exit(0)

    section(f"DOCX images: {src.name}")
    images_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src) as zf:
        media_paths = ordered_media_paths(zf)
        if not media_paths:
            warn("Встроенные изображения не найдены")

        step("Сохраняю изображения")
        manifest_images = []
        for idx, media_path in enumerate(media_paths, start=1):
            data = zf.read(media_path)
            ext = Path(media_path).suffix.lower() or mimetypes.guess_extension(
                mimetypes.guess_type(media_path)[0] or ""
            ) or ".bin"
            fig_id = f"{args.book_id}-fig-{idx:03d}"
            out_name = f"{fig_id}{ext}"
            out_path = images_dir / out_name
            out_path.write_bytes(data)

            width, height = image_size(data)
            manifest_images.append({
                "figure_id": fig_id,
                "occurrence_index": idx,
                "source_path": media_path,
                "output_file": f"images/{out_name}",
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "width": width,
                "height": height,
            })

    manifest = {
        "book_id": args.book_id,
        "source_file": src.name,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "image_count": len(manifest_images),
        "images": manifest_images,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.dump(manifest, f, allow_unicode=True, sort_keys=False)

    ok(f"Изображений: {len(manifest_images)}")
    ok(f"Манифест: {manifest_path.relative_to(manifest_path.parent.parent.parent)}")


if __name__ == "__main__":
    main()
