# Authoring spec: survey (GENERATED — do not hand-edit; re-run gen_model_map.py)

## survey-template

kind: collectionType · MCP tools: `<verb>_survey-template` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_survey-template_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `survey-templates` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `clinicallyValidated` | boolean | required; default=False |
| `description` | text | required |
| `edit` | boolean | required; default=False |
| `image` | media |  |
| `instructions` | text |  |
| `resultFeedback` | text |  |
| `surveyTemplateQuestion` | relation | manyToMany → survey-template-question |
| `title` | string | required |

## survey-template-question

kind: collectionType · MCP tools: `<verb>_survey-template-question` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_survey-template-question_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `survey-template-questions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text | required |
| `optionList` | relation | manyToMany → survey-template-question-option |
| `order` | integer |  |
| `questionType` | enumeration | required; default=singleSelect; enum: rate \| singleSelect \| multiSelect \| openText |
| `scored` | boolean | required; default=False |
| `surveyTemplates` | relation | manyToMany → survey-template |
| `title` | string | required |
