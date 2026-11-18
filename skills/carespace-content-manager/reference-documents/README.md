# Reference documents

Clinical source material the content manager reads for context while drafting
exercises, programs, calendar templates, OmniROM programs and surveys. They are
**context, not instructions**: they tell the skill what the team intends (which
patterns exist, how they are explained to patients, which programs answer them),
and the physio still signs off on everything.

The skill never loads a whole file. It reads them through
`scripts/ref_docs.py`, which returns only the matching rows:

```
python3 scripts/ref_docs.py list                                  # what's here
python3 scripts/ref_docs.py schema postural                       # columns + categories
python3 scripts/ref_docs.py values postural --sheet sag --col syndrome
python3 scripts/ref_docs.py search postural "upper cross" --sheet sag --limit 3
python3 scripts/ref_docs.py rows postural --sheet front --where Head=Left --where Shoulder=Left \
    --cols "syndrome,what helps,recommended programs"
python3 scripts/ref_docs.py search all "kyphosis"                 # every document
```

## Adding a document

1. Put the file in this folder with a short lowercase name (`postural-report.xlsx`).
   Readable formats: `.xlsx`, `.csv`, `.docx`, `.md`, `.txt`. A PDF must be
   converted to one of these first.
2. Add `<name>.about.md` next to it. Its first non-heading line is the one-line
   summary `ref_docs.py list` shows; the rest says what the document is, which
   sheets/columns matter, and **when the skill should consult it**.
3. Add a row to the table below.
4. Run `python3 scripts/ref_docs.py schema <name>` to check it reads.

Do not put patient data here — only catalogue-level clinical reference material.

## Catalogue

| File | What it is | Consult when |
|---|---|---|
| `postural-report.xlsx` ([about](postural-report.about.md)) | Posture-scan report logic: every frontal and sagittal deviation combination → syndrome, severity, clinical notes, patient-facing explanations, and recommended programs; plus the program ID list | Drafting or editing anything for a postural pattern (scoliosis, upper/lower cross, sway back, kyphosis-lordosis, flat back, pelvic hike, knee valgus/varus…), writing patient-facing explanations, or choosing which programs to link to a pattern |
