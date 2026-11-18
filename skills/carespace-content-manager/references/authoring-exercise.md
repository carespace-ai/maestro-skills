# Authoring spec: exercise (GENERATED — do not hand-edit; re-run gen_model_map.py)

## exercise

kind: collectionType · MCP tools: `<verb>_exercise` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercises` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `alignment_tips` | text |  |
| `assets` | component | repeatable assets.videos |
| `balance_demand` | enumeration | enum: supported \| standing_stable \| single_leg \| dynamic |
| `body_regions` | relation | manyToMany → body-region |
| `breathing` | text |  |
| `carespaceId` | integer | required; unique |
| `common_mistakes` | relation | manyToMany → exercise-common-mistake |
| `contraindication_status` | enumeration | required; default=unverified; enum: unverified \| none_known \| documented |
| `contraindication_tags` | text |  |
| `contraindications` | text |  |
| `cool_down_recommendations` | relation | manyToMany → exercise-cool-down-recommendation |
| `default_daily_frequency` | integer |  |
| `default_hold_seconds` | integer |  |
| `default_reps` | integer |  |
| `default_sets` | integer |  |
| `default_weekly_frequency` | integer |  |
| `description` | text |  |
| `energy_expenditure` | relation | oneToOne → exercise-energy-expenditure |
| `equipment` | relation | manyToMany → equipment |
| `equipment_alternatives` | text |  |
| `equipment_status` | enumeration | required; default=unverified; enum: unverified \| none_required \| listed |
| `exercise_categories` | relation | manyToMany → exercise-category |
| `exercise_complexity` | relation | manyToOne → exercise-complexity |
| `exercise_exclusions` | relation | manyToMany → exercise-exclusion |
| `exercise_image` | media |  |
| `exercise_positions` | relation | manyToMany → exercise-position |
| `exercise_target_muscle_groups` | relation | manyToMany → exercise-target-muscle-group |
| `exercise_video` | media |  |
| `feedback_points` | relation | manyToMany → exercise-feedback-point |
| `floor_transfer_required` | boolean |  |
| `frequency` | text |  |
| `function` | text |  |
| `functional_applications` | text |  |
| `functional_goals` | relation | manyToMany → functional-goal |
| `instructions` | text |  |
| `intensity_levels` | relation | manyToMany → exercise-intensity-level |
| `is_bilateral` | boolean |  |
| `joint_demand` | enumeration | enum: low \| moderate \| high |
| `joints` | relation | manyToMany → joint |
| `laterality` | enumeration | enum: bilateral \| left \| right \| unilateral_either |
| `machine_clearance` | enumeration | required; default=unevaluated; enum: unevaluated \| auto_cleared \| auto_blocked |
| `machine_clearance_notes` | text |  |
| `machine_cleared_at` | datetime |  |
| `machine_contraindication_class` | string |  |
| `machine_contraindications` | text |  |
| `machine_filled_fields` | text |  |
| `machine_instructions` | text |  |
| `machine_ruleset_version` | string |  |
| `modification_options` | relation | oneToOne → exercise-modification-option |
| `movement_complexity` | enumeration | enum: simple \| moderate \| complex |
| `name` | string | required |
| `orientation` | enumeration | enum: vertical \| horizontal |
| `pointBase` | relation | oneToOne → landmark |
| `pointReference` | relation | oneToOne → landmark |
| `pointsToCount` | component | single mediapipe.points |
| `precautions` | text |  |
| `premiumPlans` | relation | oneToMany → premium-plan |
| `progression_level` | enumeration | enum: beginner \| intermediate \| advanced |
| `progression_steps` | relation | manyToMany → exercise-progression-step |
| `reasons` | relation | manyToMany → reason |
| `recommended_duration` | integer |  |
| `related_exercises` | relation | oneToMany → exercise |
| `requires_assistance` | boolean |  |
| `review_notes` | text |  |
| `review_status` | enumeration | required; default=unreviewed; enum: unreviewed \| in_review \| approved \| flagged |
| `reviewed_at` | datetime |  |
| `reviewed_by` | string |  |
| `supportive_surfaces` | text |  |
| `tags` | relation | manyToMany → exercise-tag |
| `therapist_notes` | text |  |
| `trueToForm` | media |  |
| `vrImage` | media |  |
| `vrVideo` | media |  |
| `warm_up_suggestions` | relation | manyToMany → exercise-warm-up-suggestion |
| `weight_bearing` | boolean |  |

## exercise-tag

kind: collectionType · MCP tools: `<verb>_exercise-tag` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-tag_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-tags` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## functional-goal

kind: collectionType · MCP tools: `<verb>_functional-goal` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_functional-goal_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `functional-goals` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `functionalGoalReasons` | relation | manyToMany → functional-goal-reason |
| `name` | string |  |
| `program_templates` | relation | manyToMany → program-template |
| `recommendations` | relation | manyToMany → recommendation |
| `tools` | relation | manyToMany → tool |

## exercise-target-muscle-group

kind: collectionType · MCP tools: `<verb>_exercise-target-muscle-group` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-target-muscle-group_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-target-muscle-groups` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## exercise-modification-option

kind: collectionType · MCP tools: `<verb>_exercise-modification-option` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-modification-option_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-modification-options` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `level` | relation | oneToOne → exercise-modification-option-level |

## exercise-modification-option-level

kind: collectionType · MCP tools: `<verb>_exercise-modification-option-level` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-modification-option-level_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-modification-option-levels` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## exercise-common-mistake

kind: collectionType · MCP tools: `<verb>_exercise-common-mistake` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-common-mistake_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-common-mistakes` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-feedback-point

kind: collectionType · MCP tools: `<verb>_exercise-feedback-point` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-feedback-point_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-feedback-points` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-warm-up-suggestion

kind: collectionType · MCP tools: `<verb>_exercise-warm-up-suggestion` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-warm-up-suggestion_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-warm-up-suggestions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `duration` | string |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-cool-down-recommendation

kind: collectionType · MCP tools: `<verb>_exercise-cool-down-recommendation` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-cool-down-recommendation_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-cool-down-recommendations` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `duration` | string |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-progression-step

kind: collectionType · MCP tools: `<verb>_exercise-progression-step` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-progression-step_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-progression-steps` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |
| `step` | integer |  |

## component assets.videos

| field | type | constraints |
|---|---|---|
| `gender` | enumeration | required; enum: male \| female |
| `image` | media | required |
| `sideBody` | enumeration | required; enum: left \| right \| both |
| `target` | enumeration | required; default=default; enum: default \| vr \| alphaWebm \| alphaMov \| portrait |
| `video` | media | required |

## component mediapipe.points

| field | type | constraints |
|---|---|---|
| `a` | relation | oneToOne → landmark |
| `b` | relation | oneToOne → landmark |
| `c` | relation | oneToOne → landmark |
| `d` | relation | oneToOne → landmark |
