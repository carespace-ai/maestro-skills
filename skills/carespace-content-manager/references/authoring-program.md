# Authoring spec: program (GENERATED — do not hand-edit; re-run gen_model_map.py)

## program-template

kind: collectionType · MCP tools: `<verb>_program-template` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-template_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-templates` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `body_regions` | relation | manyToMany → body-region |
| `carespaceId` | integer | required; unique |
| `categories` | relation | manyToMany → exercise-category |
| `description` | text |  |
| `duration` | integer | required; default=1 |
| `durationType` | enumeration | required; default=weeks; enum: days \| weeks \| months \| years |
| `exercises` | relation | manyToMany → program-exercise-template |
| `functional_goals` | relation | manyToMany → functional-goal |
| `joints` | relation | manyToMany → joint |
| `name` | string | required |
| `postureAlignments` | relation | manyToMany → posture-alignment |
| `premiumPlans` | relation | oneToMany → premium-plan |
| `programExperienceLevels` | relation | manyToMany → program-experience-level |
| `programSubgoals` | relation | manyToMany → program-subgoal |
| `programTimeAvailabilities` | relation | manyToMany → program-time-availability |
| `programWorkoutTypes` | relation | manyToMany → program-workout-type |
| `reasons` | relation | manyToMany → reason |
| `thumbnail` | media |  |

## program-exercise-template

kind: collectionType · MCP tools: `<verb>_program-exercise-template` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-exercise-template_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-exercise-templates` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `dailyReps` | integer |  |
| `name` | string |  |
| `order` | integer |  |
| `programTemplate` | relation | manyToMany → program-template |
| `reps` | integer |  |
| `sets` | integer |  |
| `strapiExerciseId` | relation | oneToOne → exercise |
| `weeklyReps` | integer |  |
