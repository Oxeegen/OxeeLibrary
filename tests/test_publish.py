"""The publishing skill's helper: what it stages is what the library's check accepts."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pub = _load("publish", "skills/oxeelibrary-publish/scripts/publish.py")
bc = _load("build_catalog", "scripts/build_catalog.py")

META = {
    "version": "1.0.0",
    "author": "Oxeegen",
    "title": {"en": "Weekly sales report", "fr": "Rapport de ventes hebdomadaire"},
    "description": {"en": "Builds the weekly sales summary.", "fr": "Produit la synthèse hebdomadaire des ventes."},
    "tags": ["sales"],
    "keywords": {"en": ["revenue"], "fr": ["chiffre d'affaires"]},
}


@pytest.fixture
def skill(tmp_path):
    folder = tmp_path / "src" / "weekly-sales"
    (folder / "scripts").mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: weekly-sales\ndescription: >\n  Builds the weekly sales summary.\n---\n\n# Weekly Sales Skill\n",
        encoding="utf-8")
    (folder / "scripts" / "build.py").write_text("print('ok')\n", encoding="utf-8")
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "build.cpython-312.pyc").write_bytes(b"\0")
    return folder


def stage(tmp_path, skill, meta=META, **flags):
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    argv = ["stage", str(skill), "--meta", str(tmp_path / "meta.json"), "--out", str(tmp_path / "stage")]
    argv += ["--placeholder"] if flags.get("placeholder", True) else []
    return pub.main(argv)


def test_the_staged_item_passes_the_library_check(tmp_path, skill, monkeypatch):
    monkeypatch.setattr(pub, "current_version", lambda item_id: None)

    assert stage(tmp_path, skill) == 0

    monkeypatch.setattr(bc, "ROOT", tmp_path / "stage")
    (tmp_path / "stage" / "plugins").mkdir()
    catalog, problems = bc.build("b" * 40)
    assert problems == []
    assert catalog["items"][0]["files"] == ["SKILL.md", "oxeegen.yaml", "scripts/build.py"]
    assert catalog["items"][0]["title"]["fr"] == "Rapport de ventes hebdomadaire"


def test_a_personal_path_or_a_lower_version_blocks_the_stage(tmp_path, skill, monkeypatch, capsys):
    monkeypatch.setattr(pub, "current_version", lambda item_id: "1.2.0")
    (skill / "notes.md").write_text("Open C:\\Users\\herre\\Desktop\\sales.xlsx\n", encoding="utf-8")

    assert stage(tmp_path, skill) == 1
    problems = json.loads(capsys.readouterr().out)["problems"]
    assert any("personal Windows path" in p for p in problems)

    (skill / "notes.md").unlink()
    assert stage(tmp_path, skill) == 1
    assert any("the library holds 1.2.0" in p for p in json.loads(capsys.readouterr().out)["problems"])


def test_the_leak_patterns_are_the_library_checks():
    assert {k: v.pattern for k, v in pub.LEAKS.items()} == {k: v.pattern for k, v in bc.LEAKS.items()}


def test_a_new_version_removes_the_files_the_skill_dropped():
    staged = {"skills/weekly-sales/SKILL.md": "s1", "assets/weekly-sales.jpg": "a1"}
    existing = ["skills/weekly-sales/SKILL.md", "skills/weekly-sales/old.md", "assets/weekly-sales.png",
                "skills/other/SKILL.md", "assets/other.jpg"]

    entries = pub.tree_changes(staged, existing, ("skills/weekly-sales/", "assets/weekly-sales."))

    deleted = sorted(e["path"] for e in entries if e["sha"] is None)
    assert deleted == ["assets/weekly-sales.png", "skills/weekly-sales/old.md"]
