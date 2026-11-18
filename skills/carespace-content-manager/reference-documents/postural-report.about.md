# Postural Report

The posture-scan report table: for every combination of frontal and sagittal deviations it gives the syndrome, severity, clinical notes, patient-facing explanations and the programs we recommend.

Source: `Postural Report.xlsx`, added 2026-11-18.

## Sheets

| Sheet | Rows | One row is | Key columns |
|---|---|---|---|
| `FrontalView` | 729 | one front-view combination: Head, Shoulder, Trunk, Pelvis, Knee, Ankle each `Left` / `Centre` / `Right` (3⁶) | Syndrome / Pattern (28), Postural Deviations, Severity, Clinical Notes, Dev. Count, Symmetry Score, What Does This Mean, What It May Cause, What Helps, About This Posture Pattern, Recommended Programs |
| `Saggital View` (sic) | 729 | one side-view combination: Head, Shoulder, Upper Body, Pelvis, Knee, Ankle each `Forward` / `Aligned` / `Behind` | same as above, with Deviation Count and Alignment Score (19 syndromes, some rows combine several with `;`) |
| `Combined Posture Report` | 532 | one frontal syndrome × sagittal syndrome pairing | Summary, What Does This Mean, What It May Cause, What Helps, Recommended Programs |
| `Programs` | 153 | one program | `Nº ID`, Program (name) |

Severity is one of Normal, Mild, Mild-Moderate, Moderate, Moderate-Severe, Severe.

In the multi-line columns, line *n* of Clinical Notes / What Does This Mean /
What It May Cause / What Helps refers to the *n*-th deviated region of that row
(Clinical Notes separates them with ` | `).

## How the content manager uses it

- **Writing for a postural pattern** (an exercise, program or calendar template
  aimed at, say, Upper Cross Syndrome or a left pelvic hike): look the pattern up
  (`values … --col syndrome`, then `search`/`rows`) and use its Clinical Notes
  (which muscles are tight or weak) and What Helps (stretch / strengthen /
  balance intent) to frame the draft. Propose it to the physio; don't assume.
- **Patient-facing wording:** What Does This Mean, What It May Cause and About
  This Posture Pattern show the tone and reading level the report already uses
  with patients — match it in descriptions and instructions.
- **Linking programs:** Recommended Programs lists `<ID> – <name>`. Resolve the
  name against the live catalogue (catalog mirror or a Strapi lookup) before
  linking anything — **the ID's relation to Strapi's `carespaceId` is not
  confirmed**, so never write it to Strapi on the spreadsheet's word alone.
- **Gaps:** a recommended program missing from the catalogue, or a pattern with
  no recommended program, is worth pointing out to the physio as a content gap.

It is reference context, not a source of truth over the physio or the catalogue:
if it disagrees with what the physio says, the physio wins.
