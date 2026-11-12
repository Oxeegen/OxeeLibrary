---
name: oxeelibrary-publish
description: Publishes a local skill to the Oxeegen library.
version: 1.0.0
author: Oxeegen
license: MIT
required_environment_variables:
  - name: OXEELIBRARY_GITHUB_TOKEN
    prompt: GitHub token for Oxeegen/OxeeLibrary
    help: A fine-grained token limited to Oxeegen/OxeeLibrary, with Contents and Pull requests set to Read and write.
    required_for: opening the pull request
metadata:
  hermes:
    tags: [oxeegen, publishing, skills]
    category: productivity
---

# OxeeLibrary Publish Skill

Takes a skill the user built and refined in Oxee Hermes and proposes it to the Oxeegen library
(`Oxeegen/OxeeLibrary`) as a pull request, with its catalog texts in English and French and its
visual. It never publishes directly: an Oxeegen maintainer reviews and merges the pull request,
and only that merge makes the skill appear in every user's catalog.

## When to Use

- The user asks to publish, share or distribute one of their skills to Oxeegen users, or to the
  "catalogue Oxeegen", "OxeeLibrary", "la bibliothèque Oxeegen".
- The user asks to publish a new version of a skill already in the library.

Not for plugins yet, and not for skills from the hub or bundled with the app: only the user's own.

## Prerequisites

- `OXEELIBRARY_GITHUB_TOKEN`: a fine-grained GitHub token limited to `Oxeegen/OxeeLibrary` with
  **Contents** and **Pull requests** set to *Read and write*. If it is missing, tell the user how to
  create one (github.com › Settings › Developer settings › Fine-grained tokens, resource owner
  Oxeegen) and stop.
- The helper is `SKILL_DIR/scripts/publish.py`, run with `terminal`: `python SKILL_DIR/scripts/publish.py ...`.

## How to Run

```
python SKILL_DIR/scripts/publish.py scan <skill-folder>
python SKILL_DIR/scripts/publish.py current <id>
python SKILL_DIR/scripts/publish.py stage <skill-folder> --meta <meta.json> [--image <file> | --placeholder] --out <stage-folder>
python SKILL_DIR/scripts/publish.py publish <stage-folder>
python SKILL_DIR/scripts/publish.py status <pull-request-number>
```

Every command prints JSON. `stage` and `scan` exit 1 when something blocks the publication and list
each problem.

## Procedure

1. **Find the skill.** Locate the user's skill folder (the one holding its `SKILL.md`) with
   `search_files`. Its folder name is the item id. Confirm with the user which skill and folder.
2. **Scan it.** Run `scan`. Fix with the user, in their skill (not in a copy), everything it reports:
   - personal paths, account names, client names, keys or tokens: make them generic (ask the user
     for a neutral wording, or read the value from an environment variable declared in
     `required_environment_variables`);
   - a `description` longer than 60 characters or without a final period;
   - a `name` that differs from the folder name.
   Also read the skill yourself for anything personal the scan cannot see (names of real people,
   customers, internal URLs) and ask the user before keeping it.
3. **Check what the library already holds.** Run `current <id>`. If the item exists, this is a new
   version: its `version` must be higher; say what it was.
4. **Gather the catalog texts with the user.** For a new version, start from the skill's
   `oxeegen.yaml` if it has one (an installed library skill does). Propose, then let the user correct:
   - `title` (en, fr): at most 60 characters;
   - `description` (en, fr): one or two sentences, at most 200 characters, what it does for the user;
   - `tags`: 2 to 5 lowercase slugs;
   - `keywords` (en, fr): words people would type to find it;
   - `version` (X.Y.Z, 1.0.0 for a first publication) and `author` (default: "Oxeegen").
   Write them to a `meta.json` in a temporary folder:
   `{"version", "author", "title": {"en", "fr"}, "description": {"en", "fr"}, "tags": [], "keywords": {"en": [], "fr": []}}`.
5. **The visual.** Ask the user for an image; `stage --image` crops and resizes it to 2:1. Without
   one, `stage --placeholder` draws a plain Oxeegen-violet banner with the title; say it can be
   replaced later with a new version.
6. **Stage.** Run `stage` into a new temporary folder. Fix every reported problem, then run it again.
7. **Confirm, then publish.** Show the user what will be proposed (item id, version, files, texts in
   both languages) and ask for an explicit go. Then run `publish`: it opens the pull request and
   prints its address. Give it to the user.
8. **Follow the check.** Run `status <number>` a minute later. Report the result: when the check
   passes, a maintainer can merge; when it fails, read its problems, fix them in the user's skill,
   and publish again (a new pull request replaces nothing: close the failed one on GitHub).

## Pitfalls

- Never put the token in a file, a command line or the chat: the script reads it from the
  environment.
- `publish` proposes; it cannot merge. Never tell the user the skill is live before a maintainer
  merged the pull request.
- Publishing copies the skill as it is now: run `scan` again after any change.

## Verification

`status` shows the pull request open with the "Validate items and catalog" check passed.
