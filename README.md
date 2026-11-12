# OxeeLibrary

The skills and plugins Oxeegen publishes for [Oxee Hermes](https://github.com/Oxeegen/OxeeHermes).
Oxee Hermes reads `catalog.json` from this repository and offers every item in its catalog, ready
to install in one click.

```
skills/<id>/        a skill: SKILL.md (standard Agent Skills format) + oxeegen.yaml
plugins/<id>/       a Hermes plugin: plugin.yaml and its code + oxeegen.yaml
assets/<id>.jpg     the item's catalog visual (2:1)
catalog.json        built from the items by scripts/build_catalog.py: do not edit by hand
schema/             what oxeegen.yaml holds
```

Skills keep the standard [Agent Skills](https://agentskills.io/specification) format, written for
Oxee Hermes first: they can be copied into another compatible agent. Everything the catalog shows
(titles and descriptions in English and French, tags, search keywords, visual, version) lives in
the item's `oxeegen.yaml`, described in [schema/oxeegen.schema.md](schema/oxeegen.schema.md).
Plugins are Hermes plugins and run in Oxee Hermes only.

## Publishing an item

1. Create and refine the skill in Oxee Hermes.
2. Ask the agent to publish it: it copies the item, checks that nothing personal is left in it,
   asks for the catalog texts and visual, and opens a pull request here.
3. The **Validate the library** check runs on the pull request: complete metadata, a 2:1 visual,
   a valid `SKILL.md` or `plugin.yaml`, no personal path, key or token, and an up-to-date
   `catalog.json`.
4. A maintainer reviews and merges. Nothing reaches users before that merge: `main` only accepts
   reviewed pull requests that pass the check.

To publish a new version of an item, change it, bump `version` in its `oxeegen.yaml`, and open a
pull request the same way. Users who installed it see the update.

## Checking locally

```bash
pip install -r scripts/requirements.txt
python scripts/build_catalog.py          # validate every item and rebuild catalog.json
python -m pytest -q tests                # the checker's own tests
```
