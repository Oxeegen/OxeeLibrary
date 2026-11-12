"""The library check: what it accepts, what it refuses, and that catalog.json is reproducible."""

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

_spec = importlib.util.spec_from_file_location("build_catalog", Path(__file__).resolve().parents[1] / "scripts/build_catalog.py")
bc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bc)

META = """\
version: 1.0.0
author: Oxeegen
title: {en: Weekly sales report, fr: Rapport de ventes hebdomadaire}
description:
  en: Builds the weekly sales summary from your exports.
  fr: Produit la synthèse hebdomadaire des ventes à partir de vos exports.
tags: [sales, reporting]
keywords: {en: [revenue], fr: [chiffre d'affaires]}
"""
SKILL = "---\nname: weekly-sales\ndescription: Builds the weekly sales summary.\n---\n\n# Weekly Sales Skill\n"


@pytest.fixture
def library(tmp_path, monkeypatch):
    for folder in ("skills", "plugins", "assets"):
        (tmp_path / folder).mkdir()
    monkeypatch.setattr(bc, "ROOT", tmp_path)
    monkeypatch.setattr(bc, "CATALOG", tmp_path / "catalog.json")
    return tmp_path


def add_skill(root: Path, meta: str = META, skill: str = SKILL, size=(1200, 600)) -> Path:
    folder = root / "skills" / "weekly-sales"
    folder.mkdir()
    (folder / "oxeegen.yaml").write_text(meta, encoding="utf-8")
    (folder / "SKILL.md").write_text(skill, encoding="utf-8")
    Image.new("RGB", size, "purple").save(root / "assets" / "weekly-sales.jpg")
    return folder


def test_a_complete_skill_enters_the_catalog(library):
    add_skill(library)

    catalog, problems = bc.build()

    assert problems == []
    [entry] = catalog["items"]
    assert entry["id"] == "weekly-sales" and entry["type"] == "skill"
    assert entry["title"]["fr"] == "Rapport de ventes hebdomadaire"
    assert entry["image"] == "assets/weekly-sales.jpg"
    assert entry["digest"].startswith("sha256:")


def test_catalog_is_reproducible_and_check_catches_a_stale_one(library):
    folder = add_skill(library)
    assert bc.main([]) == 0
    first = (library / "catalog.json").read_text(encoding="utf-8")
    assert bc.main(["--check"]) == 0

    (folder / "SKILL.md").write_text(SKILL + "\nOne more step.\n", encoding="utf-8")

    assert bc.main(["--check"]) == 1
    assert bc.main([]) == 0
    assert json.loads(first)["items"][0]["digest"] != json.loads((library / "catalog.json").read_text())["items"][0]["digest"]


@pytest.mark.parametrize(
    ("meta", "skill", "size", "expected"),
    [
        (META.replace("fr: Rapport de ventes hebdomadaire", "fr: ''"), SKILL, (1200, 600), "title.fr: missing"),
        (META, SKILL.replace("name: weekly-sales", "name: other"), (1200, 600), "must be the folder name"),
        (META, SKILL.replace("summary.", "summary for every region and every week of the year."), (1200, 600), "at most 60"),
        (META, SKILL, (1200, 1200), "needs 2:1"),
        (META, SKILL + "\nRead C:\\Users\\herre\\Documents\\sales.xlsx\n", (1200, 600), "personal Windows path"),
        (META, SKILL + "\nUse key sk-abcdefghijklmnopqrstuvwxyz123456\n", (1200, 600), "an API key"),
    ],
)
def test_an_incomplete_or_leaky_skill_is_refused(library, meta, skill, size, expected):
    add_skill(library, meta, skill, size)

    _, problems = bc.build()

    assert any(expected in p for p in problems), problems
