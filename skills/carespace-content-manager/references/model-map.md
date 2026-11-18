# Content model map (GENERATED — do not hand-edit; re-run gen_model_map.py)

71 content types · 9 components · 70 draft-and-publish

## Dependency hubs (in-degree: how many types point at this one)

| type | referenced by |
|---|---|
| `exercise` | 21 types |
| `program-template` | 12 types |
| `body-point` | 6 types |
| `reason` | 6 types |
| `functional-goal` | 5 types |
| `omni-rom-exercise` | 5 types |
| `recommendation` | 5 types |
| `omni-rom-program` | 4 types |
| `premium-plan` | 4 types |
| `body-region` | 3 types |
| `joint` | 3 types |
| `posture-alignment` | 3 types |
| `exercise-category` | 2 types |
| `landmark` | 2 types |
| `posture-analytic` | 2 types |
| `posture-joint` | 2 types |
| `program-experience-level` | 2 types |
| `survey-template-question` | 2 types |
| `therapist` | 2 types |
| `aggravating-factor` | 1 types |
| `availability` | 1 types |
| `calendar-program-template` | 1 types |
| `equipment` | 1 types |
| `exercise-common-mistake` | 1 types |
| `exercise-complexity` | 1 types |
| `exercise-cool-down-recommendation` | 1 types |
| `exercise-energy-expenditure` | 1 types |
| `exercise-exclusion` | 1 types |
| `exercise-feedback-point` | 1 types |
| `exercise-intensity-level` | 1 types |
| `exercise-modification-option` | 1 types |
| `exercise-modification-option-level` | 1 types |
| `exercise-position` | 1 types |
| `exercise-progression-step` | 1 types |
| `exercise-tag` | 1 types |
| `exercise-target-muscle-group` | 1 types |
| `exercise-warm-up-suggestion` | 1 types |
| `functional-goal-reason` | 1 types |
| `omni-rom-exercise-group` | 1 types |
| `omni-rom-joint` | 1 types |
| `omni-rom-program-exercise` | 1 types |
| `omni-rom-reference` | 1 types |
| `omni-rom-scan-type` | 1 types |
| `pain-cause` | 1 types |
| `pain-duration` | 1 types |
| `pain-frequency` | 1 types |
| `pain-status` | 1 types |
| `program-exercise-template` | 1 types |
| `program-subgoal` | 1 types |
| `program-time-availability` | 1 types |
| `program-workout-type` | 1 types |
| `recommendation-audience` | 1 types |
| `recommendation-category` | 1 types |
| `recommendation-persona` | 1 types |
| `recommendation-type` | 1 types |
| `relieving-factor` | 1 types |
| `skill` | 1 types |
| `survey-template` | 1 types |
| `survey-template-question-option` | 1 types |
| `tag` | 1 types |
| `tool` | 1 types |

Editing a hub touches every dependent — look before you write.

## activity-stream-action

kind: collectionType · MCP tools: `<verb>_activity-stream-action` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_activity-stream-action_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `activity-stream-actions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## activity-stream-feedback

kind: collectionType · MCP tools: `<verb>_activity-stream-feedback` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_activity-stream-feedback_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `activity-stream-feedbacks` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## activity-stream-progress

kind: collectionType · MCP tools: `<verb>_activity-stream-progress` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_activity-stream-progress_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `activity-stream-progresses` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## aggravating-factor

kind: collectionType · MCP tools: `<verb>_aggravating-factor` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_aggravating-factor_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `aggravating-factors` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## audit-classification

kind: collectionType · MCP tools: `<verb>_audit-classification` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_audit-classification_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `audit-classifications` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `name` | string | required |

## availability

kind: collectionType · MCP tools: `<verb>_availability` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_availability_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `availabilities` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `day_of_the_week` | enumeration | enum: Monday \| Tuesday \| Wednesday \| Thursday \| Friday \| Saturday \| Sunday |
| `end_time` | time |  |
| `reason` | relation | manyToOne → reason |
| `start_time` | time |  |
| `therapists` | relation | manyToMany → therapist |

## body-point

kind: collectionType · MCP tools: `<verb>_body-point` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_body-point_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `body-points` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `aggravatingFactors` | relation | manyToMany → aggravating-factor |
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `painCauses` | relation | manyToMany → pain-cause |
| `painDurations` | relation | manyToMany → pain-duration |
| `painFrequencies` | relation | manyToMany → pain-frequency |
| `painStatuses` | relation | manyToMany → pain-status |
| `position` | enumeration | enum: front \| back |
| `relievingFactors` | relation | manyToMany → relieving-factor |

## body-region

kind: collectionType · MCP tools: `<verb>_body-region` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_body-region_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `body-regions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `joints` | relation | manyToMany → joint |
| `name` | string | required |
| `program_templates` | relation | manyToMany → program-template |

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

## diagnose-code

kind: collectionType · MCP tools: `<verb>_diagnose-code` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_diagnose-code_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `diagnose-codes` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `code` | string | required |
| `description` | text | required |

## equipment

kind: collectionType · MCP tools: `<verb>_equipment` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_equipment_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `equipments` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

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

## exercise-alias

kind: collectionType · MCP tools: `<verb>_exercise-alias` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-alias_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-aliases` · draftAndPublish: False

| field | type | constraints |
|---|---|---|
| `canonicalExercise` | relation | manyToOne → exercise |
| `carespaceId` | integer | required; unique |
| `retiredAt` | datetime |  |
| `retiredName` | string |  |
| `side` | enumeration | required; enum: left \| right \| none |

## exercise-category

kind: collectionType · MCP tools: `<verb>_exercise-category` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-category_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-categories` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |
| `program_templates` | relation | manyToMany → program-template |

## exercise-common-mistake

kind: collectionType · MCP tools: `<verb>_exercise-common-mistake` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-common-mistake_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-common-mistakes` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-complexity

kind: collectionType · MCP tools: `<verb>_exercise-complexity` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-complexity_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-complexities` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | oneToMany → exercise |
| `name` | string |  |

## exercise-cool-down-recommendation

kind: collectionType · MCP tools: `<verb>_exercise-cool-down-recommendation` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-cool-down-recommendation_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-cool-down-recommendations` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `duration` | string |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-energy-expenditure

kind: collectionType · MCP tools: `<verb>_exercise-energy-expenditure` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-energy-expenditure_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-energy-expenditures` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `calories_burned` | text |  |
| `carespaceId` | integer | required; unique |

## exercise-exclusion

kind: collectionType · MCP tools: `<verb>_exercise-exclusion` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-exclusion_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-exclusions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## exercise-feedback-point

kind: collectionType · MCP tools: `<verb>_exercise-feedback-point` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-feedback-point_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-feedback-points` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |

## exercise-intensity-level

kind: collectionType · MCP tools: `<verb>_exercise-intensity-level` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-intensity-level_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-intensity-levels` · draftAndPublish: True

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

## exercise-position

kind: collectionType · MCP tools: `<verb>_exercise-position` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-position_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-positions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## exercise-progression-step

kind: collectionType · MCP tools: `<verb>_exercise-progression-step` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-progression-step_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-progression-steps` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |
| `step` | integer |  |

## exercise-tag

kind: collectionType · MCP tools: `<verb>_exercise-tag` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-tag_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-tags` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## exercise-target-muscle-group

kind: collectionType · MCP tools: `<verb>_exercise-target-muscle-group` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-target-muscle-group_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-target-muscle-groups` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |

## exercise-warm-up-suggestion

kind: collectionType · MCP tools: `<verb>_exercise-warm-up-suggestion` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_exercise-warm-up-suggestion_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `exercise-warm-up-suggestions` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `duration` | string |  |
| `exercises` | relation | manyToMany → exercise |

## frontend-translation

kind: singleType · MCP tools: `<verb>_frontend-translation` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_frontend-translation_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `frontend-translations` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `Admin` | component | single translation.admin |
| `Patient` | component | single translation.patient |

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

## functional-goal-reason

kind: collectionType · MCP tools: `<verb>_functional-goal-reason` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_functional-goal-reason_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `functional-goal-reasons` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `functionalGoals` | relation | manyToMany → functional-goal |
| `name` | string | unique |

## health-sign

kind: collectionType · MCP tools: `<verb>_health-sign` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_health-sign_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `health-signs` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## informed-consent

kind: collectionType · MCP tools: `<verb>_informed-consent` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_informed-consent_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `informed-consents` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text | required |

## joint

kind: collectionType · MCP tools: `<verb>_joint` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_joint_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `joints` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyRegions` | relation | manyToMany → body-region |
| `carespaceId` | integer | required; unique |
| `exercises` | relation | manyToMany → exercise |
| `name` | string | required |
| `program_templates` | relation | manyToMany → program-template |

## landmark

kind: collectionType · MCP tools: `<verb>_landmark` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_landmark_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `landmarks` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string | required; unique |
| `value` | integer | required; unique |

## medical-history

kind: collectionType · MCP tools: `<verb>_medical-history` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_medical-history_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `medical-histories` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |

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

## omni-rom-exercise-group

kind: collectionType · MCP tools: `<verb>_omni-rom-exercise-group` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-exercise-group_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-exercise-groups` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `frontend` | component | required; single frontend.attributes |
| `key` | enumeration | enum: full \| upperBody \| upperRight \| upperLeft \| lowerBody \| lowerRight \| lowerLeft |
| `name` | string | required |
| `omniRomExercises` | relation | manyToMany → omni-rom-exercise |

## omni-rom-joint

kind: collectionType · MCP tools: `<verb>_omni-rom-joint` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-joint_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-joints` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `omniRomPrograms` | relation | manyToMany → omni-rom-program |

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

## omni-rom-reference

kind: collectionType · MCP tools: `<verb>_omni-rom-reference` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-reference_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-references` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `min` | integer | required |
| `name` | string | required |
| `normal` | integer | required |
| `omniRomExercise` | relation | oneToOne → omni-rom-exercise |
| `wfl` | integer | required |

## omni-rom-scan-type

kind: collectionType · MCP tools: `<verb>_omni-rom-scan-type` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_omni-rom-scan-type_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `omni-rom-scan-types` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `omniRomPrograms` | relation | manyToMany → omni-rom-program |

## pain-cause

kind: collectionType · MCP tools: `<verb>_pain-cause` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_pain-cause_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `pain-causes` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## pain-duration

kind: collectionType · MCP tools: `<verb>_pain-duration` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_pain-duration_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `pain-durations` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## pain-frequency

kind: collectionType · MCP tools: `<verb>_pain-frequency` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_pain-frequency_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `pain-frequencies` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## pain-status

kind: collectionType · MCP tools: `<verb>_pain-status` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_pain-status_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `pain-statuses` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## posture-alignment

kind: collectionType · MCP tools: `<verb>_posture-alignment` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_posture-alignment_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `posture-alignments` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `name` | string | required |
| `postureAnalytics` | relation | manyToMany → posture-analytic |
| `postureJoints` | relation | manyToMany → posture-joint |
| `programTemplates` | relation | manyToMany → program-template |
| `whatCause` | text |  |
| `whatHelps` | text |  |
| `whatMeans` | text |  |

## posture-analytic

kind: collectionType · MCP tools: `<verb>_posture-analytic` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_posture-analytic_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `posture-analytics` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `function` | text |  |
| `name` | string | required |
| `order` | integer | required |
| `points` | component | single mediapipe.points |
| `portraitVideo` | media |  |
| `postureAlignments` | relation | manyToMany → posture-alignment |
| `postureJoints` | relation | manyToMany → posture-joint |
| `video` | media | required |
| `view` | enumeration | required; enum: front \| left \| right \| back |

## posture-joint

kind: collectionType · MCP tools: `<verb>_posture-joint` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_posture-joint_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `posture-joints` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string | required |
| `postureAlignments` | relation | manyToMany → posture-alignment |
| `postureAnalytics` | relation | manyToMany → posture-analytic |

## premium-plan

kind: collectionType · MCP tools: `<verb>_premium-plan` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_premium-plan_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `premium-plans` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `exercise` | relation | manyToOne → exercise |
| `name` | string | required |
| `omniRomExercise` | relation | manyToOne → omni-rom-exercise |
| `omniRomProgram` | relation | manyToOne → omni-rom-program |
| `programTemplate` | relation | manyToOne → program-template |

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

## program-experience-level

kind: collectionType · MCP tools: `<verb>_program-experience-level` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-experience-level_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-experience-levels` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `programTemplates` | relation | manyToMany → program-template |

## program-subgoal

kind: collectionType · MCP tools: `<verb>_program-subgoal` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-subgoal_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-subgoals` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `programTemplates` | relation | manyToMany → program-template |

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

## program-time-availability

kind: collectionType · MCP tools: `<verb>_program-time-availability` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-time-availability_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-time-availabilities` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `programTemplates` | relation | manyToMany → program-template |

## program-workout-type

kind: collectionType · MCP tools: `<verb>_program-workout-type` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_program-workout-type_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `program-workout-types` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `programTemplates` | relation | manyToMany → program-template |

## reason

kind: collectionType · MCP tools: `<verb>_reason` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_reason_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `reasons` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `calendarProgramTemplates` | relation | manyToMany → calendar-program-template |
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `exercises` | relation | manyToMany → exercise |
| `name` | string |  |
| `omniRomExercises` | relation | manyToMany → omni-rom-exercise |
| `programTemplates` | relation | manyToMany → program-template |
| `reason_type` | enumeration | required; default=clinical; enum: clinical \| client \| internal |
| `tags` | relation | oneToMany → tag |

## recommendation

kind: collectionType · MCP tools: `<verb>_recommendation` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_recommendation_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `recommendations` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `functionalGoals` | relation | manyToMany → functional-goal |
| `media` | media |  |
| `recommendation` | richtext | required |
| `recommendationAudiences` | relation | manyToMany → recommendation-audience |
| `recommendationCategories` | relation | manyToMany → recommendation-category |
| `recommendationPersonas` | relation | manyToMany → recommendation-persona |
| `recommendationTypes` | relation | manyToMany → recommendation-type |
| `title` | string |  |

## recommendation-audience

kind: collectionType · MCP tools: `<verb>_recommendation-audience` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_recommendation-audience_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `recommendation-audiences` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `recommendations` | relation | manyToMany → recommendation |

## recommendation-category

kind: collectionType · MCP tools: `<verb>_recommendation-category` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_recommendation-category_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `recommendation-categories` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `name` | string |  |
| `recommendations` | relation | manyToMany → recommendation |

## recommendation-persona

kind: collectionType · MCP tools: `<verb>_recommendation-persona` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_recommendation-persona_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `recommendation-personas` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `description` | text |  |
| `name` | string |  |
| `recommendations` | relation | manyToMany → recommendation |

## recommendation-type

kind: collectionType · MCP tools: `<verb>_recommendation-type` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_recommendation-type_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `recommendation-types` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `recommendations` | relation | manyToMany → recommendation |

## relieving-factor

kind: collectionType · MCP tools: `<verb>_relieving-factor` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_relieving-factor_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `relieving-factors` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `bodyPoints` | relation | manyToMany → body-point |
| `carespaceId` | integer | required; unique |
| `name` | string |  |

## skill

kind: collectionType · MCP tools: `<verb>_skill` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_skill_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `skills` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string |  |
| `therapists` | relation | manyToMany → therapist |

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

## survey-template-question-option

kind: collectionType · MCP tools: `<verb>_survey-template-question-option` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_survey-template-question-option_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `survey-template-question-options` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `option` | string | required |
| `order` | integer |  |
| `questions` | relation | manyToMany → survey-template-question |
| `score` | integer | required |

## tag

kind: collectionType · MCP tools: `<verb>_tag` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_tag_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `tags` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `name` | string | required; unique |
| `reason` | relation | manyToOne → reason |

## therapist

kind: collectionType · MCP tools: `<verb>_therapist` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_therapist_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `therapists` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `availabilities` | relation | manyToMany → availability |
| `bio` | text |  |
| `carespaceId` | integer | required; unique |
| `contact_info` | component | repeatable contact.contact-information |
| `name` | string |  |
| `profile_picture` | media |  |
| `skills` | relation | manyToMany → skill |
| `years_of_experience` | integer |  |

## tool

kind: collectionType · MCP tools: `<verb>_tool` (SINGULAR uid; possible verbs: list/get/create/update/delete/publish/unpublish + `discard_tool_draft` — availability mirrors the admin token's permissions per session) · REST plural id: `tools` · draftAndPublish: True

| field | type | constraints |
|---|---|---|
| `carespaceId` | integer | required; unique |
| `functional_goals` | relation | manyToMany → functional-goal |
| `name` | string |  |

## Components

### component assets.videos

| field | type | constraints |
|---|---|---|
| `gender` | enumeration | required; enum: male \| female |
| `image` | media | required |
| `sideBody` | enumeration | required; enum: left \| right \| both |
| `target` | enumeration | required; default=default; enum: default \| vr \| alphaWebm \| alphaMov \| portrait |
| `video` | media | required |

### component calendar.day-activity

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

### component contact.contact-information

| field | type | constraints |
|---|---|---|
| `address1` | string |  |
| `address2` | string |  |
| `city` | string |  |
| `email` | email |  |
| `phone` | string |  |
| `state` | string |  |
| `website` | string |  |
| `zipcode` | string |  |

### component frontend.attributes

| field | type | constraints |
|---|---|---|
| `styles` | text |  |

### component mediapipe.points

| field | type | constraints |
|---|---|---|
| `a` | relation | oneToOne → landmark |
| `b` | relation | oneToOne → landmark |
| `c` | relation | oneToOne → landmark |
| `d` | relation | oneToOne → landmark |

### component references.age

| field | type | constraints |
|---|---|---|
| `end` | integer | required |
| `start` | integer | required |

### component references.values

| field | type | constraints |
|---|---|---|
| `min` | decimal | required |
| `normal` | decimal | required |
| `wfl` | integer |  |

### component translation.admin

| field | type | constraints |
|---|---|---|
| `data` | json | required |

### component translation.patient

| field | type | constraints |
|---|---|---|
| `data` | json | required |
