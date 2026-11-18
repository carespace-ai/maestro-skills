# Authoring spec: calendar (GENERATED — do not hand-edit; re-run gen_model_map.py)

## calendar-program-template

kind: collectionType · MCP tools: `<verb>_calendar-program-template` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_calendar-program-template_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `calendar-program-templates` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `days` | component | repeatable calendar.day-activity |
| `description` | text |  |
| `experienceLevel` | enumeration | required; default=beginner; enum: beginner \| intermediate \| advanced |
| `experienceLevelRef` | relation | manyToOne → program-experience-level |
| `name` | string | required |
| `reasons` | relation | manyToMany → reason |
| `tags` | json |  |
| `thumbnail` | media |  |
| `weeks` | integer | required; default=1 |

## component calendar.day-activity

| field | type | constraints |
|---|---|---|
| `activityType` | enumeration | required; enum: survey \| evaluation \| exercise \| omniRom \| posture \| bodyComposition |
| `dayNumber` | integer | required |
| `exerciseItems` | relation | manyToMany → program-exercise-template |
| `exerciseProgram` | relation | oneToOne → program-template |
| `omniRomExercises` | relation | manyToMany → omni-rom-program-exercise |
| `omniRomProgram` | relation | oneToOne → omni-rom-program |
| `order` | integer | default=0 |
| `surveyTemplate` | relation | oneToOne → survey-template |
