# `oxeegen.yaml`, the catalog metadata of an item

Every item, `skills/<id>/` or `plugins/<id>/`, carries an `oxeegen.yaml` beside its native files
(`SKILL.md` for a skill, `plugin.yaml` for a plugin). The native files stay standard; everything
the Oxee Hermes catalog shows lives here. `scripts/build_catalog.py` validates it, and builds
`catalog.json` on every merge into `main`.

```yaml
version: 1.0.0                 # X.Y.Z; bump it with every change you publish
author: Oxeegen                # who to credit
min_app_version: 0.8.5         # optional: the oldest Oxee Hermes that can install it
title:
  en: Weekly sales report      # at most 60 characters
  fr: Rapport de ventes hebdomadaire
description:                   # at most 200 characters, shown on the catalog card
  en: Builds the weekly sales summary from your exports, with a table by region.
  fr: Produit la synthèse hebdomadaire des ventes à partir de vos exports, avec un tableau par région.
tags: [sales, reporting]       # lowercase slugs, used by the catalog filters
keywords:                      # extra words the catalog search matches, per language
  en: [revenue, region, weekly]
  fr: [chiffre d'affaires, région, hebdomadaire]
```

The item's `id` is its folder name (lowercase letters, digits, dashes). Its type comes from the
folder it sits in (`skills/` or `plugins/`).

## Required alongside

| File | Rule |
|---|---|
| `skills/<id>/SKILL.md` | Standard Agent Skills format. `name` is the folder name; `description` is one sentence, at most 60 characters, ending with a period (Hermes' own rule). `version` equals `oxeegen.yaml`'s: Oxee Hermes reads it on an installed skill to offer a newer one (the publish skill sets it). |
| `plugins/<id>/plugin.yaml` | Hermes plugin manifest. `name` is the folder name. |
| `assets/<id>.jpg` or `.png` | The catalog visual: 2:1 (e.g. 1200x600), at least 800 px wide, at most 500 KB. Its left half dark and empty, the subject on the right half, no text: Oxee Hermes sets the title, description, keywords and install button on the left half. |

## What the check refuses

Anything that would ship the author's machine or accounts to every user: a personal path
(`C:\Users\<name>\…`, `/home/<name>/…`), an API key, a GitHub token, a private key.
