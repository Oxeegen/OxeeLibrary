# Maintainer skills

Skills for Oxeegen maintainers, the people who publish to this library. They are **not** in the
catalog: Oxee Hermes users never see them. The check still holds them to the `SKILL.md` rules and
the leak scan.

| Skill | What it does |
|---|---|
| `oxeelibrary-publish` | Proposes one of your skills to the library as a pull request. Needs `OXEELIBRARY_GITHUB_TOKEN`: a fine-grained token limited to `Oxeegen/OxeeLibrary`, with Contents and Pull requests set to Read and write. |

## Installing them in Oxee Hermes

Ask your Oxee Hermes, for example: *« Installe les skills maintainers d'Oxeegen/OxeeLibrary »*.
The agent does the following; you can also do it by hand.

1. List the folders of `maintainers/` on the `main` branch:
   `https://api.github.com/repos/Oxeegen/OxeeLibrary/contents/maintainers?ref=main`
   (the repository is public: no token needed to read it).
2. For each skill folder, download every file it holds, keeping the folder layout
   (`https://api.github.com/repos/Oxeegen/OxeeLibrary/contents/maintainers/<skill>?ref=main`, then
   each subfolder), into the Oxee Hermes skills folder:
   - Windows: `%LOCALAPPDATA%\hermes-oxeegen\skills\<skill>\`
   - macOS: `~/Library/Application Support/hermes-oxeegen/skills/<skill>/`
3. Replace the whole folder when updating, so a file removed upstream does not linger.
4. Start a new conversation: the skill is picked up there.
