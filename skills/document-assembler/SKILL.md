---
name: document-assembler
description: Assemble des pièces docx/pdf en un livrable final propre.
version: 0.8.0
author: Julien Herrera, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [documents, docx, pdf, assemblage, office]
    related_skills: [genoffice, pdf]
---

# Document Assembler

Transformer un lot de pièces (docx, md, PDF, images) en un **livrable unique soigné** : page de garde, sommaire, pagination, en-tête/pied de page, styles cohérents, export PDF final contrôlé. C'est un orchestrateur : le contenu vient des pièces (jamais réécrit), le moteur est OxeeOffice/GenOffice (commandes `genoffice`), la fusion PDF éventuelle est le skill `pdf`. Ce n'est PAS un merge binaire de docx (fragile : styles, sections, en-têtes) ni un mail-merge (`genoffice merge`) ni un créateur de deck/workbook.

## When to Use

- « Assemble / regroupe / fusionne ces documents en un seul », « un seul PDF propre avec sommaire ».
- Dossier de candidature ou administratif (lettre + bulletins + avis → un PDF), rapport avec annexes, bundle de documents.
- Suite d'un brief `goal-definer` dont le livrable est un document assemblé.
- **Don't use for** : créer un document simple (`genoffice create --type docx --from` suffit), publipostage (`genoffice merge`), decks (`genoffice create --type pptx`), diff entre versions (document-comparator).

## Questionnaire d'entrée (obligatoire)

Dès que le skill est déclenché, poser **une seule question groupée** via `clarify` (1 invocation, 3–4 questions au maximum) — jamais de questions éparpillées ensuite. Questions et options **dynamiques** :

1. **Format de sortie** — options calculées selon les formats d'entrée : entrées éditables (docx/md/html/xlsx/pptx) présentes → `docx + pdf (recommandé)` / `pdf seul` / `docx seul` ; entrées PDF ou scans uniquement → `pdf (fusion, recommandé)` / `docx (si couche texte)`. L'UI ajoute un champ libre « Autre » : l'utiliser tel quel.
2. **Sommaire ?** → `Oui (recommandé)` / `Non`. Si Oui : mode `field` si le livrable principal est un .docx (ou PDF sans annexes), mode `static` si PDF final avec pièces `append` (numéros réels exigés).
3. **Numérotation des pages ?** → `Oui — « Page N sur M » (recommandé)` / `Oui — numéro seul` / `Non`.
4. **Charte graphique ?** → posée **uniquement** si des brands existent : `python <skill_dir de brand-kit>/scripts/brand_kit.py list` non vide (hors exemples) → proposer `Appliquer la charte <slug> (nom)` / `Aucune`. Sinon, ne pas poser la question.

Les réponses alimentent le manifeste (voir plus bas). Si une réponse manque ou est évasive : appliquer le défaut recommandé **sans re-demander**. Si une charte est retenue : charger le brand (`brand-kit` → `json <slug>`), puis appliquer **la déclinaison document/PDF de la skill `brand-kit`** (son fichier `references/pdf-declination.md`) : page de garde (bandeau `primary`, titre `primary_fg`, sous-titre `muted`, titres `primary`), pieds de page stampés aux couleurs du brand (filet `secondary`, **nom du document** — jamais le nom de la charte, « Page N / M ») — et `tone.voice` pour les textes rédigés ; le mentionner dans les remarques.

## Exécution discrète (anti-verbosité)

- **Dès le début** : `todo_list` avec les étapes exactes, dans l'ordre : Récupération des fichiers → Lecture des fichiers → Conversion → Mise en page → Sommaire → Fusion → Numérotation → Relecture → Récapitulatif (adapter à la demande, 1 ligne par étape, `merge: false`).
- Chaque étape terminée **et vérifiée** → `completed` (jamais sur intention ; une étape bloquée reste en cours avec une seule phrase d'explication + la `suggestion` fournie par genoffice).
- Pendant l'exécution : **aucune prose narrative**. Au maximum une ligne « Étape X/N — nom » ; les détails techniques ne s'affichent que sur demande ou en cas d'erreur. Pas de chemins de travail intermédiaires, pas de commentaires sur les commandes.

## Prerequisites

- OxeeOffice/GenOffice installé : `genoffice capabilities --json` → `status: ok` et app installée. Sinon : fallback « Mode réduit » (voir Pitfalls), ne pas promettre les fonctionnalités complètes.
- Règles d'invocation : voir la skill `genoffice` (launcher, `cmd.exe /c '...\genoffice.cmd ...'` sur ce poste, jamais `node genoffice.cjs` pour Word/Markdown, `--json` en lecture programme, pas d'espace dans `--out` de travail, `output_exists` → autre nom ou `--force`).
- Fusion/numérotation des PDF finaux : pymupdf via `uv run --with pymupdf python <script>` (pas de dépendance locale).

## Manifeste d'entrée

Le skill part d'un manifeste JSON (à confirmer avec l'utilisateur, ou dérivé du brief) :

```json
{
  "output": "dossier-candidature",
  "cover": {"title": "Dossier de candidature — L. Herrera Mazza", "subtitle": "Collège Sainte Trinité — rentrée 2027", "date": "2026-11-12"},
  "toc": "field",
  "parts": [
    {"path": "lettre-motivation.md",        "role": "body",    "title": "1. Lettre de motivation"},
    {"path": "bulletins.docx",             "role": "body",    "title": "2. Bulletins scolaires"},
    {"path": "avis-imposition.pdf",        "role": "append",  "title": "Annexe — Avis d'imposition"}
  ]
}
```

Rôles : `body` = contenu intégré (converti/inséré), `append` = PDF ajouté tel quel en fin de document (fusion pymupdf, couleurs du brand appliquées au tampon), `cover` = page de garde. `toc` : `field` (champ Word, défaut) ou `static` (numéros réels dans le PDF final — voir « Sommaire »).

## Procédure

1. **Cadrer (questionnaire)** : une seule invocation `clarify` (voir « Questionnaire d'entrée »), puis dériver le manifeste (ordre, rôles, titre de couverture). Critère : 1 invocation, réponses toutes exploitées, défauts appliqués sans re-demander.
2. **Vérifier le moteur** : `terminal(command="genoffice capabilities --json")` → app installée ? Sinon Mode réduit (Pitfalls) et en informer l'utilisateur.
3. **Lire les pièces** (jamais dézipper le fichier Office ni le lire en texte brut) : docx → `genoffice convert <f> --to md` (ou `docs read --full`) ; PDF → `genoffice pdf read <f> --full --json` ; md/html → lu directement. Critère : chaque partie `body` a un texte source propre, titres de chapitre identifiés.
4. **Construire le master** : `write_file` d'un `master.md` = page de garde (titre, sous-titre, date) + sommaire (titres + `..... @@P<n>@@` si `toc: static`) + chapitres dans l'ordre (titres H1/H2 selon hiérarchie, contenu des pièces). Critère : un chapitre = un titre H1, aucun contenu perdu.
5. **Créer le docx** : `genoffice create --type docx --from master.md --out build/<output>.docx --json` (chemin de travail SANS espaces, ex. sous le scratch dir). Critère : `status: ok`.
6. **Ops de mise en forme** (`docs apply --ops ops.json`) : `set_page_setup` (marges A4), `set_header_footer` (**seulement si pas de tampon pymupdf à l'étape 9**, `kind: "footer"`, texte avec `{PAGE}` / `{NUMPAGES}`), et selon `toc` : `insertToc { afterBlockIndex: <index du titre de garde> }` (champ TOC, « fails if the document has no headings » — vérifier `docs read` au préalable) ou rien (mode static). Critère : `applied == total` (batch atomique, sinon corriger l'op rejeté et renvoyer tout).
7. **QA gate** : `genoffice docs check <f> --json` → traiter les vraies anomalies (`broken_ref`, `placeholder_left` sauf placeholders voulus, `field_not_evaluated` = TOC/PAGE : info, Word calcule à l'ouverture) ; puis `genoffice render <f> --out shots --json` et **regarder chaque PNG** (`vision_analyze`) : garde, sommaire, sauts de page, pied de page. 2 tours de correction max, puis rapport.
8. **Sommaire static (si `toc: static`)** : export PDF provisoire (étape 9) → `genoffice pdf read <pdf> --full --json` → pour chaque chapitre, trouver la page où la ligne de titre apparaît **sans points** (une ligne de sommaire contient `.....` et `@@P<n>@@`, le titre du chapitre est exactement `1. Titre`) → `docs apply` `findReplace` de chaque `@@P<n>@@` par le numéro trouvé → ré-exporter. Si la pagination décale après substitution : re-détecter, au plus 2 itérations ; si instable → revenir à `toc: field` et le signaler.
9. **Exporter** : `genoffice convert <f> --to pdf --out <output>.pdf --json` ; si des pièces `append`, les fusionner en ordre (pymupdf : `uv run --with pymupdf python merge.py`) et **numéroter toutes les pages après fusion** (« Page N sur M », tampon bas-centre) — dans ce cas, ne pas mettre de pied de page dans le docx (étape 6), sinon double affichage. Critère : PDF ouvert et premier/dernier feuillets lus.
10. **Récapitulatif final** : bloc court (voir section dédiée) — sommaire réel, lien, remarques. Critère : ≤ 8 lignes hors sommaire, aucune étape re-déroulée, aucune commande citée.

## Récapitulatif final (template)

Terminer par ce bloc, jamais par un récit des étapes :

> **Document assemblé — 19 pages**  
> - p. 3 — Courrier de motivation  
> - p. 6 — Bulletins scolaires (copies scannées)  
> - p. 17 — Avis d'imposition 2025  
> **Fichier :** (voir la ligne `MEDIA:` ci-dessous)  
> **Remarques :** <une ligne par limite ou choix, ou « aucune »>

Puis, **dans la même réponse**, la ligne `MEDIA:` **sur sa propre ligne, hors bloc, sans backticks et jamais en chemin de code** — c'est elle seule qui déclenche la carte fichier du chat (boutons « Ouvrir le dossier parent » / « Ouvrir l'aperçu ») :

`MEDIA:C:/Users/<user>/Desktop/.../livrable.pdf`

Règles absolues : chemin absolu ; uniquement des `/` (jamais `\` ni `C:\...`) ; un fichier par ligne `MEDIA:` ; une ligne `MEDIA:` par livrable si plusieurs ; ne jamais noyer le chemin dans le texte ou dans des backticks (aucune carte). Le sommaire du bloc reprend le sommaire réel du document (pages vérifiées).

## Sommaire — le choix honnête

| Mode | Résultat docx | Résultat PDF exporté | Usage |
|---|---|---|---|
| `field` (`insertToc`) | parfait, Word calcule à l'ouverture | **numéros absents** (l'exporteur GenOffice n'évalue pas le champ TOC) | livrable .docx, ou PDF sans numéros accepté |
| `static` (2 passes) | texte fixe (numéros figés) | numéros corrects | livrable PDF exigé |

Le mode `static` est la seule voie pour un PDF aux numéros corrects : valider en relisant le PDF final (`pdf read`) et confirmer que chaque ligne de sommaire porte le bon numéro.

Affinage v0.2 (identifié sur cas réel, non encore codé) : remplacer les points littéraux `.........` par des **tabulations avec leader pointillé** (op `setParagraphFormat` `tabs` : `pos`, `leader: "dot"`) pour des numéros alignés à droite ; page de garde plus aérée (espacement vertical).

## Pitfalls

- **TOC `field` sans numéros dans le PDF** : comportement vérifié (test 2026-11) — l'exporteur ne calcule pas le champ TOC ; ne pas promettre des numéros dans un PDF en mode field.
- **`setParagraphFormat.spaceBefore`/`spaceAfter` : numériques (twips, 1200 = 60 pt)** — les chaînes `"48pt"` sont rejetées par cet op (contrairement à `define_style.paragraph`) ; vérifié 2026-11.
- **`set_header_footer` exige `kind: "header"|"footer"`** (op rejeté sinon) ; `{PAGE}`/`{NUMPAGES}` deviennent des champs PAGE dont Word recompute le résultat — `docs check` les signale `field_not_evaluated` (info, pas une erreur).
- **`set_header_footer` avec `text: ""` ne supprime PAS un champ PAGE existant** (vérifié 2026-11 : le champ reste, seul le texte littéral part, et le rendu montre le numéro seul) — pour un pied de page vidé, reconstruire le docx sans l'op, ou garder le champ et ne pas tamponner par-dessus.
- **Index de blocs vivants** : après `insertToc`/`insert_content`, les index changent — relire `docs read` avant de cibler un bloc dans un batch suivant.
- **`render` = seule vérité de mise en page** : un `docs check` vert ne dit rien de la mise en page ; regarder chaque PNG avant de livrer.
- **`placeholder_left`** signale lorem ipsum / TODO / `[insert …]` : ne pas laisser de lorem ipsum dans un livrable final (vérifier et purger).
- **`create`/`convert` refusent d'écraser** (`output_exists`, exit 2) : autre nom ou `--force` (uniquement sur demande).
- **Fichier ouvert dans OxeeOffice** → `file_open_in_gui` : demander de fermer l'onglet ou écrire vers `--out`.
- **Mode réduit (pas d'app)** : personnaliser avec python-docx (skill `docx`) — pas de champs TOC/PAGE (sommaire texte sans numéros), pas de `render` (contrôle par `docx` skill), le signaler à l'utilisateur. `convert docx→pdf` et `render` exigent l'app.
- **Chemin de travail** : sans espaces (la chaîne bash→cmd→`%*` casse les espaces dans `--out`) ; générer dans le scratch dir puis copier vers le chemin final.

## Verification

- [ ] Questionnaire `clarify` : 1 invocation, options dynamiques selon entrées, charte proposée seulement si brands existants
- [ ] `todo_list` créé au départ, chaque étape marquée `completed` seulement après vérification
- [ ] Manifeste et mode de sommaire validés ; moteur détecté (app installée ou Mode réduit annoncé)
- [ ] `docs check` : aucune `broken_ref`, aucun placeholder indésirable
- [ ] `render` : chaque page regardée (garde + sommaire + chapitres + pied de page)
- [ ] PDF final relu (`pdf read`) : couverture, sommaire numéroté (mode static) ou absence de numéros signalée, annexes présentes
- [ ] Si charte retenue : garde et pieds de page aux couleurs du brand (bandeau `primary`, filet `secondary`), libellé de pied = **nom du document** (pas le brand)
- [ ] Récapitulatif final : bloc court avec sommaire réel + ligne `MEDIA:` autonome (chemin absolu en `/`, hors code) = carte fichier visible, remarques
