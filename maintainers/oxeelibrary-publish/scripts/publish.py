#!/usr/bin/env python3
"""Propose a local skill to the Oxeegen library (Oxeegen/OxeeLibrary) as a pull request.

    publish.py scan <skill-folder>                      what would block the publication
    publish.py current <id>                             the version the library holds, if any
    publish.py stage <skill-folder> --meta <meta.json> [--image <file> | --placeholder] --out <dir>
                                                        the item laid out as in the library, checked
    publish.py publish <stage-dir>                      branch + commit + pull request (needs the token)
    publish.py status <number>                          the pull request and its check

Standard library only, plus Pillow for the visual (shipped with Oxee Hermes). Every command prints
JSON. The checks mirror the library's own (scripts/build_catalog.py), which runs again on the pull
request and has the last word. The token comes from OXEELIBRARY_GITHUB_TOKEN, never an argument.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = "Oxeegen/OxeeLibrary"
API = f"https://api.github.com/repos/{REPO}"
TOKEN_VAR = "OXEELIBRARY_GITHUB_TOKEN"
CHECK_NAME = "Validate items and catalog"
LANGS = ("en", "fr")

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SKILL_DESCRIPTION_MAX = 60
TITLE_MAX = 60
DESCRIPTION_MAX = 200
IMAGE_SIZE = (1200, 600)
IMAGE_MAX_BYTES = 500 * 1024
SKIPPED = {".git", "__pycache__", ".DS_Store", ".pytest_cache", ".venv", "node_modules"}

# Same patterns as the library's check (scripts/build_catalog.py LEAKS).
LEAKS = {
    "a personal Windows path": re.compile(r"[A-Za-z]:\\\\?Users\\\\?[^\\\s]+", re.I),
    "a personal home path": re.compile(r"(?<![\w.])/(?:home|Users)/[a-z][\w.-]+/"),
    "an API key": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})"),
    "a GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "a private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
TEXT_SUFFIXES = {".md", ".txt", ".py", ".js", ".mjs", ".ts", ".sh", ".ps1", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}


def out(payload: dict, ok: bool = True) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


# --- the skill itself ------------------------------------------------------------------------

def frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar keys of a SKILL.md frontmatter (enough for name and description)."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    lines = match.group(1).splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in (">", ">-", "|", "|-"):
            block = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                block.append(nxt.strip())
            value = " ".join(b for b in block if b)
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def skill_files(folder: Path) -> list[Path]:
    """The skill's files, without caches and without a previous oxeegen.yaml (stage writes a new one)."""
    return sorted(p for p in folder.rglob("*")
                  if p.is_file() and not SKIPPED.intersection(p.relative_to(folder).parts) and p.suffix != ".pyc"
                  and p.relative_to(folder).as_posix() != "oxeegen.yaml")


def scan_skill(folder: Path) -> tuple[str, list[str]]:
    """The item id and everything that would block its publication."""
    problems: list[str] = []
    item_id = folder.name
    if not SLUG.match(item_id):
        problems.append(f"folder name {item_id!r}: lowercase letters, digits and dashes only")
    skill = folder / "SKILL.md"
    if not skill.is_file():
        return item_id, problems + ["SKILL.md: missing"]
    front = frontmatter(skill.read_text(encoding="utf-8"))
    if front.get("name") != item_id:
        problems.append(f"SKILL.md: name is {front.get('name')!r}, must be the folder name {item_id!r}")
    description = front.get("description", "")
    if not description or len(description) > SKILL_DESCRIPTION_MAX or not description.endswith("."):
        problems.append(f"SKILL.md: description must be one sentence ending with a period, at most {SKILL_DESCRIPTION_MAX} characters (now {len(description)})")
    for path in skill_files(folder):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for what, pattern in LEAKS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path.relative_to(folder).as_posix()}:{line}: contains {what}")
    return item_id, problems


# --- catalog metadata ------------------------------------------------------------------------

def check_meta(meta: dict) -> list[str]:
    problems = []
    if not SEMVER.match(str(meta.get("version", ""))):
        problems.append("version: X.Y.Z")
    if meta.get("min_app_version") and not SEMVER.match(str(meta["min_app_version"])):
        problems.append("min_app_version: X.Y.Z")
    if not str(meta.get("author", "")).strip():
        problems.append("author: missing")
    for key, limit in (("title", TITLE_MAX), ("description", DESCRIPTION_MAX)):
        value = meta.get(key) or {}
        for lang in LANGS:
            text = str(value.get(lang, "")).strip() if isinstance(value, dict) else ""
            if not text:
                problems.append(f"{key}.{lang}: missing")
            elif len(text) > limit:
                problems.append(f"{key}.{lang}: {len(text)} characters, at most {limit}")
    tags = meta.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) and SLUG.match(t) for t in tags):
        problems.append("tags: a list of lowercase slugs")
    keywords = meta.get("keywords", {})
    if not isinstance(keywords, dict) or not all(isinstance(keywords.get(lang, []), list) for lang in LANGS):
        problems.append("keywords: {\"en\": [...], \"fr\": [...]}")
    return problems


def meta_yaml(meta: dict) -> str:
    """oxeegen.yaml from the metadata. JSON strings are valid YAML scalars: no YAML library needed."""
    q = lambda value: json.dumps(str(value), ensure_ascii=False)  # noqa: E731
    lines = [f"version: {meta['version']}", f"author: {q(meta['author'])}"]
    if meta.get("min_app_version"):
        lines.append(f"min_app_version: {meta['min_app_version']}")
    for key in ("title", "description"):
        lines.append(f"{key}:")
        lines += [f"  {lang}: {q(meta[key][lang].strip())}" for lang in LANGS]
    lines.append(f"tags: [{', '.join(meta.get('tags', []))}]")
    lines.append("keywords:")
    for lang in LANGS:
        lines.append(f"  {lang}: [{', '.join(q(k) for k in meta.get('keywords', {}).get(lang, []))}]")
    return "\n".join(lines) + "\n"


# --- the visual ------------------------------------------------------------------------------

def make_visual(target: Path, image: Path | None, title: str) -> list[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return ["the visual needs Pillow (python -m pip install Pillow)"]
    if image:
        with Image.open(image) as source:
            picture = source.convert("RGB")
        width, height = picture.size
        if width / height > 2:   # too wide: keep the centre
            new_width = height * 2
            picture = picture.crop(((width - new_width) // 2, 0, (width + new_width) // 2, height))
        else:                    # too tall: keep the centre
            new_height = width // 2
            picture = picture.crop((0, (height - new_height) // 2, width, (height + new_height) // 2))
        if picture.size[0] < 800:
            return [f"visual: {image.name} is too small, at least 800x400 is needed"]
        picture = picture.resize(IMAGE_SIZE, Image.LANCZOS)
    else:
        picture = Image.new("RGB", IMAGE_SIZE)
        draw = ImageDraw.Draw(picture)
        for x in range(IMAGE_SIZE[0]):   # Oxeegen violet, darker to the right
            shade = x / IMAGE_SIZE[0]
            draw.line([(x, 0), (x, IMAGE_SIZE[1])], fill=(int(108 - 60 * shade), int(76 - 50 * shade), int(242 - 110 * shade)))
        try:
            font = ImageFont.load_default(size=64)
        except TypeError:
            font = ImageFont.load_default()
        draw.text((80, IMAGE_SIZE[1] // 2), title, font=font, fill="white", anchor="lm")
    for quality in (88, 80, 70, 60):
        picture.save(target, "JPEG", quality=quality, optimize=True)
        if target.stat().st_size <= IMAGE_MAX_BYTES:
            return []
    return [f"visual: still {target.stat().st_size // 1024} KB at the lowest quality, use a simpler image"]


# --- GitHub ----------------------------------------------------------------------------------

def github(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict | list:
    request = urllib.request.Request(
        f"{API}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "oxeelibrary-publish",
                 "X-GitHub-Api-Version": "2022-11-28", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:300]
        raise SystemExit(out({"error": f"GitHub {method} {path}: HTTP {error.code}", "detail": detail}, ok=False)) from None


def token() -> str:
    value = os.environ.get(TOKEN_VAR, "").strip()
    if not value:
        raise SystemExit(out({"error": f"{TOKEN_VAR} is not set: create a fine-grained token limited to {REPO} "
                                        "(Contents and Pull requests: Read and write)"}, ok=False))
    return value


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def current_version(item_id: str) -> str | None:
    request = urllib.request.Request(f"https://raw.githubusercontent.com/{REPO}/main/skills/{item_id}/oxeegen.yaml",
                                     headers={"User-Agent": "oxeelibrary-publish"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    match = re.search(r"^version:\s*['\"]?(\d+\.\d+\.\d+)", text, re.M)
    return match.group(1) if match else None


def tree_changes(staged: dict[str, str], existing: list[str], item_paths: tuple[str, ...]) -> list[dict]:
    """New blobs for every staged file, and a deletion for each file the item no longer has."""
    entries = [{"path": path, "mode": "100644", "type": "blob", "sha": sha} for path, sha in sorted(staged.items())]
    for path in existing:
        if path.startswith(item_paths) and path not in staged:
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
    return entries


# --- commands --------------------------------------------------------------------------------

def cmd_scan(args) -> int:
    item_id, problems = scan_skill(Path(args.skill).resolve())
    return out({"id": item_id, "problems": problems}, ok=not problems)


def cmd_current(args) -> int:
    version = current_version(args.id)
    return out({"id": args.id, "in_library": version is not None, "version": version})


def cmd_stage(args) -> int:
    source = Path(args.skill).resolve()
    item_id, problems = scan_skill(source)
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    problems += check_meta(meta)
    stage = Path(args.out).resolve()
    if stage.exists():
        shutil.rmtree(stage)
    item = stage / "skills" / item_id
    item.mkdir(parents=True)
    for path in skill_files(source):
        target = item / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    if not check_meta(meta):
        (item / "oxeegen.yaml").write_text(meta_yaml(meta), encoding="utf-8")
    (stage / "assets").mkdir()
    if args.image or args.placeholder:
        problems += make_visual(stage / "assets" / f"{item_id}.jpg", Path(args.image) if args.image else None,
                                str(meta.get("title", {}).get("en", item_id)))
    else:
        problems.append("visual: pass --image <file> or --placeholder")
    previous = None if problems else current_version(item_id)
    if previous and SEMVER.match(str(meta.get("version", ""))) and version_key(meta["version"]) <= version_key(previous):
        problems.append(f"version: the library holds {previous}, publish a higher one")
    (stage / "publish.json").write_text(json.dumps({"id": item_id, "kind": "skills", "version": meta.get("version"),
                                                    "previous": previous, "title": meta.get("title")},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file() and p.name != "publish.json")
    return out({"id": item_id, "version": meta.get("version"), "previous": previous, "files": files, "problems": problems},
               ok=not problems)


def cmd_publish(args) -> int:
    stage = Path(args.stage).resolve()
    info = json.loads((stage / "publish.json").read_text(encoding="utf-8"))
    auth = token()
    item_id, version = info["id"], info["version"]
    item_paths = (f"skills/{item_id}/", f"assets/{item_id}.")

    main_sha = github("GET", "/git/ref/heads/main", token=auth)["object"]["sha"]
    base_tree = github("GET", f"/git/commits/{main_sha}", token=auth)["tree"]["sha"]
    existing = [e["path"] for e in github("GET", f"/git/trees/{base_tree}?recursive=1", token=auth)["tree"] if e["type"] == "blob"]

    staged = {}
    for path in sorted(p for p in stage.rglob("*") if p.is_file() and p.name != "publish.json"):
        blob = github("POST", "/git/blobs", {"content": base64.b64encode(path.read_bytes()).decode(), "encoding": "base64"}, auth)
        staged[path.relative_to(stage).as_posix()] = blob["sha"]

    tree = github("POST", "/git/trees", {"base_tree": base_tree, "tree": tree_changes(staged, existing, item_paths)}, auth)
    action = "Update" if info.get("previous") else "Add"
    message = f"{action} skill {item_id} {version}"
    commit = github("POST", "/git/commits", {"message": message, "tree": tree["sha"], "parents": [main_sha]}, auth)
    branch = f"publish/{item_id}-{version}-{int(time.time())}"
    github("POST", "/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}, auth)
    title = info.get("title") or {}
    body = (f"{action} the skill **{title.get('en', item_id)}** ({title.get('fr', '')}), version {version}"
            + (f", replacing {info['previous']}" if info.get("previous") else "") + ".\n\n"
            "Proposed from Oxee Hermes with the oxeelibrary-publish skill. Merging publishes it in the catalog.")
    pull = github("POST", "/pulls", {"title": message, "head": branch, "base": "main", "body": body}, auth)
    return out({"pull_request": pull["html_url"], "number": pull["number"], "branch": branch})


def cmd_status(args) -> int:
    auth = os.environ.get(TOKEN_VAR) or None
    pull = github("GET", f"/pulls/{args.number}", token=auth)
    runs = github("GET", f"/commits/{pull['head']['sha']}/check-runs", token=auth).get("check_runs", [])
    check = next((r for r in runs if r["name"] == CHECK_NAME), None)
    return out({
        "pull_request": pull["html_url"], "state": "merged" if pull.get("merged") else pull["state"],
        "check": (check["conclusion"] or check["status"]) if check else "not started",
        "check_details": check["html_url"] if check else None,
    })


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan").add_argument("skill")
    commands.add_parser("current").add_argument("id")
    stage = commands.add_parser("stage")
    stage.add_argument("skill")
    stage.add_argument("--meta", required=True)
    visual = stage.add_mutually_exclusive_group()
    visual.add_argument("--image")
    visual.add_argument("--placeholder", action="store_true")
    stage.add_argument("--out", required=True)
    commands.add_parser("publish").add_argument("stage")
    commands.add_parser("status").add_argument("number", type=int)
    args = parser.parse_args(argv)
    return {"scan": cmd_scan, "current": cmd_current, "stage": cmd_stage, "publish": cmd_publish, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
