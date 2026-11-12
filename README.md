# OxeeLibrary

The skills and plugins Oxeegen publishes for [Oxee Hermes](https://github.com/Oxeegen/OxeeHermes).
Oxee Hermes reads the catalog published on the [`catalog` release](https://github.com/Oxeegen/OxeeLibrary/releases/tag/catalog)
and offers every item in its catalog, ready to install in one click.

```
skills/<id>/        a skill: SKILL.md (standard Agent Skills format) + oxeegen.yaml
plugins/<id>/       a Hermes plugin: plugin.yaml and its code + oxeegen.yaml
assets/<id>.jpg     the item's catalog visual (2:1)
schema/             what oxeegen.yaml holds
scripts/            build_catalog.py: validates the items and builds catalog.json
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
   a valid `SKILL.md` or `plugin.yaml`, no personal path, key or token.
4. A maintainer reviews and merges. Nothing reaches users before that merge: `main` only accepts
   pull requests that pass the check. The merge publishes the new `catalog.json` on the `catalog`
   release (**Publish the catalog** workflow); it names the merged commit, and the app installs
   every item from that exact commit.

To publish a new version of an item, change it, bump `version` in its `oxeegen.yaml`, and open a
pull request the same way. Users who installed it see the update.

## Checking locally

```bash
pip install -r scripts/requirements.txt
python scripts/build_catalog.py --check  # validate every item
python -m pytest -q tests                # the checker's own tests
```
