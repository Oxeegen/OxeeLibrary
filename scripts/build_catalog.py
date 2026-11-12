#!/usr/bin/env python3
"""Validate every item of the library and build catalog.json, the index Oxee Hermes reads.

    python scripts/build_catalog.py --check                          # validate only (pull requests)
    python scripts/build_catalog.py --out catalog.json --commit SHA  # validate, then build

An item is a folder skills/<id>/ (a SKILL.md, standard Agent Skills format) or plugins/<id>/ (a
Hermes plugin.yaml), plus its oxeegen.yaml (the catalog metadata, see schema/oxeegen.schema.md)
and its visual assets/<id>.jpg|png. catalog.json is not kept on main: every merge into main
publishes it alone on the `catalog` branch (.github/workflows/publish-catalog.yml).
It names the commit it was built from, so the app downloads each item's files at that exact commit;
each entry lists its files and a digest of them, which the app checks after download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 1
KINDS = {"skills": "skill", "plugins": "plugin"}
LANGS = ("en", "fr")

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
# Hermes' own rule for a skill description (skills/AGENTS.md): one sentence, at most 60 characters.
SKILL_DESCRIPTION_MAX = 60
CATALOG_DESCRIPTION_MAX = 200
IMAGE_EXTENSIONS = (".jpg", ".png")
IMAGE_MIN_WIDTH = 800
IMAGE_MAX_BYTES = 500 * 1024

# Nothing of the author's machine or accounts may ship to every user.
LEAKS = {
    "a personal Windows path": re.compile(r"[A-Za-z]:\\\\?Users\\\\?[^\\\s]+", re.I),
    "a personal home path": re.compile(r"(?<![\w.])/(?:home|Users)/[a-z][\w.-]+/"),
    "an API key": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})"),
    "a GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "a private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".mjs", ".ts", ".sh", ".ps1", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}


def _frontmatter(path: Path) -> dict:
    match = re.match(r"^---\s*\n(.*?)\n---", path.read_text(encoding="utf-8"), re.DOTALL)
    data = yaml.safe_load(match.group(1)) if match else None
    return data if isinstance(data, dict) else {}


def _files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def digest(folder: Path) -> str:
    """sha256 over each file's relative path and content, in path order."""
    h = hashlib.sha256()
    for path in _files(folder):
        h.update(path.relative_to(folder).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return "sha256:" + h.hexdigest()


def _localized(meta: dict, key: str, problems: list[str], limit: int | None = None) -> dict:
    value = meta.get(key)
    if not isinstance(value, dict):
        problems.append(f"{key}: needs an 'en' and an 'fr' text")
        return {}
    for lang in LANGS:
        text = value.get(lang)
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{key}.{lang}: missing")
        elif limit and len(text) > limit:
            problems.append(f"{key}.{lang}: {len(text)} characters, at most {limit}")
    return {lang: str(value.get(lang, "")).strip() for lang in LANGS}


def _image(item_id: str, problems: list[str]) -> str:
    found = [ROOT / "assets" / f"{item_id}{ext}" for ext in IMAGE_EXTENSIONS if (ROOT / "assets" / f"{item_id}{ext}").exists()]
    if not found:
        problems.append(f"visual: add assets/{item_id}.jpg (or .png), 2:1, at least {IMAGE_MIN_WIDTH} px wide")
        return ""
    path = found[0]
    if path.stat().st_size > IMAGE_MAX_BYTES:
        problems.append(f"visual: {path.stat().st_size // 1024} KB, at most {IMAGE_MAX_BYTES // 1024} KB")
    with Image.open(path) as image:
        width, height = image.size
    if width < IMAGE_MIN_WIDTH or abs(width / height - 2) > 0.04:
        problems.append(f"visual: {width}x{height}, needs 2:1 and at least {IMAGE_MIN_WIDTH} px wide")
    return path.relative_to(ROOT).as_posix()


def _native(kind: str, folder: Path, item_id: str, problems: list[str]) -> None:
    if kind == "skill":
        skill = folder / "SKILL.md"
        if not skill.exists():
            problems.append("SKILL.md: missing")
            return
        front = _frontmatter(skill)
        if front.get("name") != item_id:
            problems.append(f"SKILL.md: name is {front.get('name')!r}, must be the folder name {item_id!r}")
        description = str(front.get("description") or "")
        if not description or len(description) > SKILL_DESCRIPTION_MAX or not description.endswith("."):
            problems.append(f"SKILL.md: description must be one sentence ending with a period, at most {SKILL_DESCRIPTION_MAX} characters")
    else:
        manifest = folder / "plugin.yaml"
        if not manifest.exists():
            problems.append("plugin.yaml: missing")
            return
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or data.get("name") != item_id:
            problems.append(f"plugin.yaml: name must be the folder name {item_id!r}")


def _leaks(folder: Path, problems: list[str]) -> None:
    for path in _files(folder):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for what, pattern in LEAKS.items():
            if pattern.search(text):
                problems.append(f"{path.relative_to(folder).as_posix()}: contains {what}")


def build_item(kind: str, folder: Path) -> tuple[dict | None, list[str]]:
    item_id = folder.name
    problems: list[str] = []
    if not SLUG.match(item_id):
        problems.append("folder name: lowercase letters, digits and dashes only")
    meta_path = folder / "oxeegen.yaml"
    if not meta_path.exists():
        return None, ["oxeegen.yaml: missing"]
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    if not isinstance(meta, dict):
        return None, ["oxeegen.yaml: not a mapping"]

    version = str(meta.get("version", ""))
    if not SEMVER.match(version):
        problems.append("version: X.Y.Z")
    min_app = meta.get("min_app_version")
    if min_app is not None and not SEMVER.match(str(min_app)):
        problems.append("min_app_version: X.Y.Z")
    tags = meta.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) and SLUG.match(t) for t in tags):
        problems.append("tags: a list of lowercase slugs")
    keywords = meta.get("keywords") or {}
    if not isinstance(keywords, dict) or not all(isinstance(keywords.get(lang, []), list) for lang in LANGS):
        problems.append("keywords: {en: [...], fr: [...]}")
    author = meta.get("author")
    if not isinstance(author, str) or not author.strip():
        problems.append("author: missing")

    title = _localized(meta, "title", problems, 60)
    description = _localized(meta, "description", problems, CATALOG_DESCRIPTION_MAX)
    image = _image(item_id, problems)
    _native(kind, folder, item_id, problems)
    _leaks(folder, problems)

    entry = {
        "id": item_id,
        "type": kind,
        "version": version,
        "title": title,
        "description": description,
        "tags": sorted(tags) if isinstance(tags, list) else [],
        "keywords": {lang: sorted(str(k) for k in keywords.get(lang, [])) for lang in LANGS} if isinstance(keywords, dict) else {},
        "author": str(author or ""),
        "min_app_version": str(min_app) if min_app else None,
        "path": folder.relative_to(ROOT).as_posix(),
        "files": [p.relative_to(folder).as_posix() for p in _files(folder)],
        "image": image,
        "digest": digest(folder),
    }
    return entry, problems


def build(commit: str = "") -> tuple[dict, list[str]]:
    items, problems = [], []
    seen: set[str] = set()
    for folder_name, kind in KINDS.items():
        for folder in sorted(p for p in (ROOT / folder_name).iterdir() if p.is_dir()):
            entry, item_problems = build_item(kind, folder)
            problems += [f"{folder_name}/{folder.name}: {p}" for p in item_problems]
            if entry:
                if entry["id"] in seen:
                    problems.append(f"{folder_name}/{folder.name}: the id is already used by another item")
                seen.add(entry["id"])
                items.append(entry)
    # Maintainer skills: installed by hand by Oxeegen maintainers, never in the catalog, but held to
    # the same SKILL.md rules and the same leak scan.
    maintainers = ROOT / "maintainers"
    for folder in sorted(p for p in maintainers.iterdir() if p.is_dir()) if maintainers.is_dir() else []:
        found: list[str] = []
        _native("skill", folder, folder.name, found)
        _leaks(folder, found)
        problems += [f"maintainers/{folder.name}: {p}" for p in found]
    for asset in sorted((ROOT / "assets").glob("*")):
        if asset.is_file() and asset.stem not in seen and asset.name != ".gitkeep":
            problems.append(f"assets/{asset.name}: no item named {asset.stem!r}")
    return {"format": FORMAT, "repository": "Oxeegen/OxeeLibrary", "commit": commit, "items": items}, problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate every item, write nothing")
    mode.add_argument("--out", type=Path, help="where to write catalog.json")
    parser.add_argument("--commit", default="", help="the commit the catalog is built from (with --out)")
    args = parser.parse_args(argv)

    if args.out and not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("--out needs --commit <40-hex sha>")
    catalog, problems = build(args.commit)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        return 1
    if args.check:
        print(f"{len(catalog['items'])} item(s) valid")
        return 0
    args.out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(catalog['items'])} items, commit {args.commit[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
