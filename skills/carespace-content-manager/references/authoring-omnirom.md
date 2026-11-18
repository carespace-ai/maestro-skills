# Authoring spec: omnirom (GENERATED — do not hand-edit; re-run gen_model_map.py)

## omni-rom-program

kind: collectionType · MCP tools: `<verb>_omni-rom-program` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-program_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-programs` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `estimatedMinutes` | integer |  |
| `estimatedSeconds` | integer |  |
| `exercises` | relation | oneToMany → omni-rom-program-exercise |
| `frontend` | component | single frontend.attributes |
| `omniRomJoints` | relation | manyToMany → omni-rom-joint |
| `omniRomScanTypes` | relation | manyToMany → omni-rom-scan-type |
| `premiumPlans` | relation | oneToMany → premium-plan |
| `title` | string | required |

## omni-rom-program-exercise

kind: collectionType · MCP tools: `<verb>_omni-rom-program-exercise` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-program-exercise_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-program-exercises` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `OmniRomExerciseId` | relation | oneToOne → omni-rom-exercise |
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `omniRomProgram` | relation | manyToOne → omni-rom-program |
| `order` | integer | required |

## omni-rom-exercise

kind: collectionType · MCP tools: `<verb>_omni-rom-exercise` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-exercise_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-exercises` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `assets` | component | repeatable assets.videos |
| `bodySideTitle` | string |  |
| `cameraPosition` | enumeration | required; default=facing_front; enum: facing_front \| facing_back \| left_side \| right_side \| facing_front_seated \| left_side_seated \| right_side_seated |
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `function` | text | required |
| `image` | media | required |
| `mobilityMapper` | enumeration | required; enum: rightShoulder \| leftShoulder \| rightElbow \| leftElbow \| rightHip \| leftHip \| rightKnee \| leftKnee \| squat \| neck \| lumbar \| leftWrist \| rightWrist |
| `movementTitle` | string |  |
| `name` | string | required |
| `omniRomExerciseGroups` | relation | manyToMany → omni-rom-exercise-group |
| `order` | integer | required; unique |
| `pointsToCalculateAngle` | component | single mediapipe.points |
| `pointsToValidatePosition` | component | single mediapipe.points |
| `portraitImage` | media |  |
| `portraitVideo` | media |  |
| `premiumPlans` | relation | oneToMany → premium-plan |
| `reasons` | relation | manyToMany → reason |
| `reference` | relation | oneToOne → omni-rom-reference |
| `video` | media | required |

## component assets.videos

| field | type | constraints |
|---|---|---|
| `gender` | enumeration | required; enum: male \| female |
| `image` | media | required |
| `sideBody` | enumeration | required; enum: left \| right \| both |
| `target` | enumeration | required; default=default; enum: default \| vr \| alphaWebm \| alphaMov \| portrait |
| `video` | media | required |

## component frontend.attributes

| field | type | constraints |
|---|---|---|
| `styles` | text |  |

## component mediapipe.points

| field | type | constraints |
|---|---|---|
| `a` | relation | oneToOne → landmark |
| `b` | relation | oneToOne → landmark |
| `c` | relation | oneToOne → landmark |
| `d` | relation | oneToOne → landmark |
