import json, os, tempfile, unittest
from test_mcp_client import FakeTransport, rpc_result
import mcp_client
from runners import compose_program, compose_survey, compose_calendar, publish_chain
from runners.common import Job

def make_job(plan, records=None):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "plan.json"), "w") as fh:
        json.dump(plan, fh)
    os.makedirs(os.path.join(d, "records"))
    for name, rec in (records or {}).items():
        with open(os.path.join(d, "records", f"{name}.json"), "w") as fh:
            json.dump(rec, fh)
    return Job(d)

PROG_PLAN = {"kind": "compose-program", "env": "e", "title": "t",
    "program": {"name": "P", "duration": 4, "durationType": "weeks",
                "body_regions": ["Lower Limb"], "joints": [], "functional_goals": [], "reasons": []},
    "sessions_per_week": 3,
    "exercises": [{"carespaceId": 78, "documentId": "exA", "sets": 2, "reps": 10, "order": 1}]}

class TestComposeProgram(unittest.TestCase):
    def test_validate_catches_missing_dosing_and_docid(self):
        bad = json.loads(json.dumps(PROG_PLAN))
        del bad["exercises"][0]["sets"]; del bad["exercises"][0]["documentId"]
        problems = compose_program.validate(bad, {})
        self.assertTrue(any("sets" in p for p in problems))
        self.assertTrue(any("documentId" in p for p in problems))

    def test_run_creates_joins_then_program_with_connect_and_derived_dosing(self):
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "exA", "publishedAt": None}}),   # get exercise
            rpc_result({"results": [{"name": "Lower Limb", "documentId": "br1"}],
                        "pagination": {"total": 1}}),                           # resolve body_regions (pre-write)
            rpc_result({"results": [{"carespaceId": 9}], "pagination": {}}),    # next join id
            rpc_result({"data": {"documentId": "j1", "carespaceId": 10, "publishedAt": None}}),
            rpc_result({"results": [{"carespaceId": 100}], "pagination": {}}),  # next program id
            rpc_result({"data": {"documentId": "P1", "carespaceId": 101, "publishedAt": None,
                                 "exercises": {"count": 1}}}),                  # create program
            rpc_result({"data": {"documentId": "P1", "exercises": {"count": 1}}}),  # read-back
        ])
        job = make_job(PROG_PLAN)
        c = mcp_client.McpClient("u", "a", transport=ft)
        rc = compose_program.run(job, c)
        self.assertFalse(rc)
        create_join = [p for p in ft.sent if p.get("params", {}).get("name") ==
                       "create_program-exercise-template"][0]["params"]["arguments"]["data"]
        self.assertEqual(create_join["dailyReps"], 20)      # sets*reps
        self.assertEqual(create_join["weeklyReps"], 60)     # daily*sessions
        create_prog = [p for p in ft.sent if p.get("params", {}).get("name") ==
                       "create_program-template"][0]["params"]["arguments"]["data"]
        self.assertEqual(create_prog["exercises"], {"connect": [{"documentId": "j1"}]})
        self.assertIn("program", job.state["steps"])

    def test_validate_catches_duplicate_order(self):
        bad = json.loads(json.dumps(PROG_PLAN))
        dup = json.loads(json.dumps(bad["exercises"][0]))
        dup["carespaceId"] = 79
        dup["documentId"] = "exB"
        bad["exercises"].append(dup)   # both exercises now have order=1
        problems = compose_program.validate(bad, {})
        self.assertTrue(any("duplicate order" in p for p in problems))

    def test_validate_catches_duplicate_carespaceId(self):
        bad = json.loads(json.dumps(PROG_PLAN))
        dup = json.loads(json.dumps(bad["exercises"][0]))
        dup["order"] = 2            # distinct order so only carespaceId collides
        dup["documentId"] = "exB"
        bad["exercises"].append(dup)   # both exercises now have carespaceId 78
        problems = compose_program.validate(bad, {})
        self.assertTrue(any("duplicate carespaceId" in p for p in problems))

    def test_run_resolves_taxonomy_before_any_join_write(self):
        # A bad taxonomy name must fail BEFORE any join create is sent.
        plan = json.loads(json.dumps(PROG_PLAN))
        plan["program"]["functional_goals"] = ["Nonexistent Goal"]
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "exA", "publishedAt": None}}),   # get exercise (verify)
            rpc_result({"results": [{"name": "Lower Limb", "documentId": "br1"}],
                        "pagination": {"total": 1}}),                           # resolve body_regions OK
            rpc_result({"results": [], "pagination": {"total": 0}}),            # resolve functional_goals -> miss
        ])
        job = make_job(plan)
        c = mcp_client.McpClient("u", "a", transport=ft)
        with self.assertRaises(mcp_client.VocabMiss):
            compose_program.run(job, c)
        names = [p.get("params", {}).get("name") for p in ft.sent]
        self.assertNotIn("create_program-exercise-template", names)   # no write happened

    def test_resume_skips_created_join(self):
        job = make_job(PROG_PLAN)
        job.record("exercise:78", {"documentId": "exA"})
        job.record("join:1", {"documentId": "j1", "carespaceId": 10})
        ft = FakeTransport([
            rpc_result({"results": [{"name": "Lower Limb", "documentId": "br1"}],
                        "pagination": {"total": 1}}),                           # resolve body_regions (pre-write)
            rpc_result({"results": [{"carespaceId": 100}], "pagination": {}}),  # next program id
            rpc_result({"data": {"documentId": "P1", "carespaceId": 101, "publishedAt": None,
                                 "exercises": {"count": 1}}}),
            rpc_result({"data": {"documentId": "P1", "exercises": {"count": 1}}}),
        ])
        c = mcp_client.McpClient("u", "a", transport=ft)
        self.assertFalse(compose_program.run(job, c))
        names = [p.get("params", {}).get("name") for p in ft.sent]
        self.assertNotIn("create_program-exercise-template", names)   # skipped
        self.assertNotIn("get_exercise", names)                       # skipped

SURV_PLAN = {"kind": "compose-survey", "env": "e", "title": "t",
    "questions": [{"title": "Q1", "description": "d", "questionType": "rate",
                   "scored": True, "order": 1}],
    "template": {"title": "S", "description": "sd", "clinicallyValidated": False, "edit": False}}

class TestComposeSurvey(unittest.TestCase):
    def test_run_creates_questions_then_template(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                       # next q id -> 1
            rpc_result({"data": {"documentId": "q1", "publishedAt": None}}),
            rpc_result({"results": [], "pagination": {}}),                       # next tpl id
            rpc_result({"data": {"documentId": "s1", "publishedAt": None,
                                 "surveyTemplateQuestion": {"count": 1}}}),
            rpc_result({"data": {"documentId": "s1", "surveyTemplateQuestion": {"count": 1}}}),
        ])
        job = make_job(SURV_PLAN)
        self.assertFalse(compose_survey.run(job, mcp_client.McpClient("u", "a", transport=ft)))
        tpl = [p for p in ft.sent if p.get("params", {}).get("name") ==
               "create_survey-template"][0]["params"]["arguments"]["data"]
        self.assertEqual(tpl["surveyTemplateQuestion"], {"connect": [{"documentId": "q1"}]})
        self.assertFalse(tpl["clinicallyValidated"])
        names = [p.get("params", {}).get("name") for p in ft.sent]
        self.assertIn("get_survey-template", names)   # read-back call pinned

    def test_validate_catches_duplicate_order(self):
        bad = json.loads(json.dumps(SURV_PLAN))
        dup = json.loads(json.dumps(bad["questions"][0]))
        bad["questions"].append(dup)   # both questions now have order=1
        problems = compose_survey.validate(bad, {})
        self.assertTrue(any("duplicate order" in p for p in problems))

    def test_run_aborts_when_question_not_draft(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                       # next q id -> 1
            rpc_result({"data": {"documentId": "q1", "publishedAt": "2024-01-01T00:00:00.000Z"}}),
        ])
        job = make_job(SURV_PLAN)
        c = mcp_client.McpClient("u", "a", transport=ft)
        with self.assertRaises(RuntimeError):
            compose_survey.run(job, c)

CAL_PLAN = {"kind": "compose-calendar", "env": "e", "title": "t",
    "template": {"name": "C", "weeks": 1, "experienceLevel": "beginner"},
    "days": [{"dayNumber": 1, "order": 0, "activityType": "exercise",
              "ref": {"type": "program-template", "documentId": "P1"}},
             {"dayNumber": 2, "order": 0, "activityType": "evaluation"}]}

class TestComposeCalendar(unittest.TestCase):
    def test_validate_bounds_and_gating(self):
        bad = json.loads(json.dumps(CAL_PLAN))
        bad["template"]["weeks"] = 99
        bad["days"][1]["ref"] = {"type": "survey-template", "documentId": "S"}  # evaluation gates none
        problems = compose_calendar.validate(bad, {})
        self.assertTrue(any("weeks" in p for p in problems))
        self.assertTrue(any("evaluation" in p for p in problems))

    def test_run_assembles_gated_inline_days(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                      # next id
            rpc_result({"data": {"documentId": "C1", "publishedAt": None}}),    # create
            rpc_result({"data": {"documentId": "C1", "days": [                  # read-back (populate:*)
                {"dayNumber": 1, "order": 0, "exerciseProgram": {"count": 1}},  # gated relation persisted
                {"dayNumber": 2, "order": 0}]}}),                               # evaluation gates none
        ])
        job = make_job(CAL_PLAN)
        self.assertFalse(compose_calendar.run(job, mcp_client.McpClient("u", "a", transport=ft)))
        data = [p for p in ft.sent if p.get("params", {}).get("name") ==
                "create_calendar-program-template"][0]["params"]["arguments"]["data"]
        self.assertEqual(data["days"][0]["exerciseProgram"], "P1")
        self.assertNotIn("surveyTemplate", data["days"][0])
        self.assertNotIn("exerciseProgram", data["days"][1])
        get = [p for p in ft.sent if p.get("params", {}).get("name") ==
               "get_calendar-program-template"][0]["params"]["arguments"]
        self.assertEqual(get["populate"], "*")   # read-back must populate gated relations

    def test_run_raises_when_gated_day_relation_absent_on_readback(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                      # next id
            rpc_result({"data": {"documentId": "C1", "publishedAt": None}}),    # create
            rpc_result({"data": {"documentId": "C1",                            # read-back:
                                 "days": [{"dayNumber": 1, "order": 0},         # day1 lost exerciseProgram
                                          {"dayNumber": 2, "order": 0}]}}),
        ])
        job = make_job(CAL_PLAN)
        c = mcp_client.McpClient("u", "a", transport=ft)
        with self.assertRaises(RuntimeError):
            compose_calendar.run(job, c)

    def test_run_verifies_each_activity_on_a_shared_day(self):
        """A day holds several activities — assessment, survey and exercise on day 1.
        Verification must check each component on its own, not collapse them by day."""
        plan = {"kind": "compose-calendar", "env": "e", "title": "t",
                "template": {"name": "C", "weeks": 1, "experienceLevel": "beginner"},
                "days": [{"dayNumber": 1, "order": 0, "activityType": "evaluation"},
                         {"dayNumber": 1, "order": 1, "activityType": "survey",
                          "ref": {"type": "survey-template", "documentId": "S1"}},
                         {"dayNumber": 1, "order": 2, "activityType": "exercise",
                          "ref": {"type": "program-template", "documentId": "P1"}}]}
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                      # next id
            rpc_result({"data": {"documentId": "C1", "publishedAt": None}}),    # create
            rpc_result({"data": {"documentId": "C1", "days": [                  # read-back
                {"dayNumber": 1, "order": 0},                                   # evaluation gates none
                {"dayNumber": 1, "order": 1, "surveyTemplate": {"count": 1}},
                {"dayNumber": 1, "order": 2, "exerciseProgram": {"count": 1}}]}}),
        ])
        job = make_job(plan)
        self.assertFalse(compose_calendar.run(job, mcp_client.McpClient("u", "a", transport=ft)))

    def test_run_raises_when_one_activity_on_a_shared_day_lost_its_link(self):
        plan = {"kind": "compose-calendar", "env": "e", "title": "t",
                "template": {"name": "C", "weeks": 1, "experienceLevel": "beginner"},
                "days": [{"dayNumber": 1, "order": 0, "activityType": "survey",
                          "ref": {"type": "survey-template", "documentId": "S1"}},
                         {"dayNumber": 1, "order": 1, "activityType": "exercise",
                          "ref": {"type": "program-template", "documentId": "P1"}}]}
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                      # next id
            rpc_result({"data": {"documentId": "C1", "publishedAt": None}}),    # create
            rpc_result({"data": {"documentId": "C1", "days": [                  # read-back:
                {"dayNumber": 1, "order": 0},                                   # survey lost its link
                {"dayNumber": 1, "order": 1, "exerciseProgram": {"count": 1}}]}}),
        ])
        job = make_job(plan)
        c = mcp_client.McpClient("u", "a", transport=ft)
        with self.assertRaises(RuntimeError):
            compose_calendar.run(job, c)

PUB_PLAN = {"kind": "publish-chain", "env": "e", "title": "t",
    "approved_by": "luis@carespace.ai", "approved_at": "2026-07-24T00:00:00Z",
    "targets": [{"type": "survey-template-question", "documentId": "q1", "label": "Q1"},
                {"type": "survey-template", "documentId": "s1", "label": "S"}]}

class TestPublishChain(unittest.TestCase):
    def test_refuses_without_approval(self):
        bad = {k: v for k, v in PUB_PLAN.items() if k != "approved_by"}
        problems = publish_chain.validate(bad, {})
        self.assertTrue(any("approved_by" in p for p in problems))

    def test_publishes_in_order_and_verifies_last(self):
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "q1"}}),                          # publish q
            rpc_result({"data": {"documentId": "s1"}}),                          # publish s
            rpc_result({"data": {"documentId": "s1", "publishedAt": "2026"}}),   # verify
        ])
        job = make_job(PUB_PLAN)
        self.assertFalse(publish_chain.run(job, mcp_client.McpClient("u", "a", transport=ft)))
        names = [p.get("params", {}).get("name") for p in ft.sent if p.get("method") == "tools/call"]
        self.assertEqual(names, ["publish_survey-template-question", "publish_survey-template",
                                 "get_survey-template"])

    def test_disabled_probe_emits_click_list_and_rc2(self):
        ft = FakeTransport([(200, json.dumps({"jsonrpc": "2.0", "id": 1, "result":
            {"isError": True, "content": [{"type": "text",
             "text": "MCP error -32602: Tool publish_survey-template-question disabled"}]}}))])
        job = make_job(PUB_PLAN)
        rc = publish_chain.run(job, mcp_client.McpClient("u", "a", transport=ft))
        self.assertEqual(rc, 2)
        with open(os.path.join(job.dir, "log.txt")) as fh:
            logtxt = fh.read()
        self.assertIn("Q1", logtxt)          # click list names every target, in order
        self.assertIn("s1", logtxt)

from runners import scan_fill

SF_PLAN = {"kind": "scan-fill", "env": "e", "title": "t", "batch": [322]}
SF_REC = {
    "documentId": "EX322",
    "scalars": {"name": "Bird Dog", "laterality": "right"},
    "relations": {"joints": ["Lumbar Spine"]},
    "classA": {"tags": ["Core Stability"]},
    "classb": {
        "progression_steps": [{"step": 2, "description": "b"}, {"step": 1, "description": "a"}],
        "modification_options": {"description": "Seated.", "level": "Beginner"}}}

class TestScanFill(unittest.TestCase):
    def test_validate_rejects_noncanonical_classA(self):
        rec = json.loads(json.dumps(SF_REC))
        rec["classA"]["tags"] = ["Yoga Flow"]
        problems = scan_fill.validate(SF_PLAN, {"322": rec},
            standard={"tags": ["Core Stability"], "functional_goals": [],
                      "exercise_target_muscle_groups": [], "modification_option_level": ["Beginner"]})
        self.assertTrue(any("Yoga Flow" in p for p in problems))

    def test_validate_requires_record_file_per_batch_entry(self):
        problems = scan_fill.validate(SF_PLAN, {}, standard={"tags": [], "functional_goals": [],
            "exercise_target_muscle_groups": [], "modification_option_level": []})
        self.assertTrue(any("322" in p for p in problems))

    def test_run_orders_steps_creates_mod_level_via_update_and_full_doc_update(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                        # next ps id
            rpc_result({"data": {"documentId": "ps1"}}),                          # step 1 (sorted!)
            rpc_result({"data": {"documentId": "ps2"}}),                          # step 2
            rpc_result({"results": [], "pagination": {}}),                        # next mod id
            rpc_result({"data": {"documentId": "m1", "carespaceId": 1}}),         # create mod
            rpc_result({"results": [{"name": "Beginner", "documentId": "lvl1"}],
                        "pagination": {"total": 1}}),                             # resolve level
            rpc_result({"data": {"documentId": "m1"}}),                           # update mod w/ level
            rpc_result({"results": [{"name": "Core Stability", "documentId": "tag1"}],
                        "pagination": {"total": 1}}),                             # resolve tags
            rpc_result({"results": [{"name": "Lumbar Spine", "documentId": "j1"}],
                        "pagination": {"total": 1}}),                             # resolve joints
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None,
                                 "review_status": "unreviewed"}}),                # update exercise
        ])
        job = make_job(SF_PLAN, records={"322": SF_REC})
        rc = scan_fill.run(job, mcp_client.McpClient("u", "a", transport=ft),
            standard={"tags": ["Core Stability"], "functional_goals": [],
                      "exercise_target_muscle_groups": [], "modification_option_level": ["Beginner"]})
        self.assertFalse(rc)
        calls = [p["params"] for p in ft.sent if p.get("method") == "tools/call"]
        ps = [c["arguments"]["data"] for c in calls
              if c["name"] == "create_exercise-progression-step"]
        self.assertEqual([p["step"] for p in ps], [1, 2])                 # sorted by step
        upd_mod = [c for c in calls if c["name"] == "update_exercise-modification-option"][0]
        self.assertEqual(upd_mod["arguments"]["data"]["level"], "lvl1")   # bare string at UPDATE
        upd_ex = [c for c in calls if c["name"] == "update_exercise"][0]["arguments"]["data"]
        self.assertEqual(upd_ex["review_status"], "unreviewed")           # neutral, never approving
        self.assertEqual(upd_ex["carespaceId"], 322)
        self.assertEqual(upd_ex["tags"], {"connect": [{"documentId": "tag1"}]})
        self.assertEqual(upd_ex["modification_options"], "m1")

    def test_run_aborts_when_classb_create_not_draft(self):
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                     # next ps id
            rpc_result({"data": {"documentId": "ps1",
                                 "publishedAt": "2024-01-01T00:00:00.000Z"}}),  # step lands published!
        ])
        rec = {"documentId": "EX322",
               "classb": {"progression_steps": [{"step": 1, "description": "a"}]}}
        job = make_job(SF_PLAN, records={"322": rec})
        c = mcp_client.McpClient("u", "a", transport=ft)
        with self.assertRaises(RuntimeError):
            scan_fill.run(job, c, standard={"tags": [], "functional_goals": [],
                "exercise_target_muscle_groups": [], "modification_option_level": []})

    def test_validate_rejects_mod_option_missing_description(self):
        rec = json.loads(json.dumps(SF_REC))
        del rec["classb"]["modification_options"]["description"]   # canonical level, no description
        problems = scan_fill.validate(SF_PLAN, {"322": rec},
            standard={"tags": ["Core Stability"], "functional_goals": [],
                      "exercise_target_muscle_groups": [], "modification_option_level": ["Beginner"]})
        self.assertTrue(any("modification_options.description" in p for p in problems))

    # --- completeness gate (scan-fill must fill everything) ---
    COMPLETE_STANDARD = {"tags": ["Core Stability"], "functional_goals": ["Injury Prevention"],
                         "exercise_target_muscle_groups": ["Gluteus Maximus"],
                         "modification_option_level": ["Beginner"]}

    def _complete_rec(self):
        return {
            "documentId": "EX322",
            "scalars": {
                "laterality": "bilateral", "movement_complexity": "simple", "joint_demand": "low",
                "balance_demand": "supported", "progression_level": "beginner",
                "weight_bearing": False, "floor_transfer_required": True, "requires_assistance": False,
                "equipment_status": "none_required", "contraindication_status": "unverified",
                "default_sets": 3, "default_reps": 10, "default_hold_seconds": 3,
                "default_daily_frequency": 1, "default_weekly_frequency": 3,
                "instructions": "Do the thing.", "description": "A thing."},
            "relations": {"exercise_positions": ["Supine"], "joints": ["Hip"],
                          "body_regions": ["Hip"], "reasons": ["Hip pain"]},
            "classA": {"tags": ["Core Stability"], "functional_goals": ["Injury Prevention"],
                       "exercise_target_muscle_groups": ["Gluteus Maximus"]},
            "classb": {"common_mistakes": [{"description": "x"}], "feedback_points": [{"description": "x"}],
                       "warm_up_suggestions": [{"description": "x", "duration": "1m"}],
                       "cool_down_recommendations": [{"description": "x", "duration": "1m"}],
                       "progression_steps": [{"step": 1, "description": "x"}],
                       "modification_options": {"description": "x", "level": "Beginner"}}}

    def test_validate_blocks_incomplete_record(self):
        rec = {"documentId": "EX322", "scalars": {"name": "Bird Dog"}}   # almost everything missing
        problems = scan_fill.validate(SF_PLAN, {"322": rec}, standard=self.COMPLETE_STANDARD)
        for needed in ("laterality", "movement_complexity", "default_sets", "instructions",
                       "classA.tags", "classb.common_mistakes", "relations.joints"):
            self.assertTrue(any(needed in p and "required" in p for p in problems),
                            f"expected a completeness problem for {needed}")

    def test_validate_passes_complete_record(self):
        problems = scan_fill.validate(SF_PLAN, {"322": self._complete_rec()},
                                      standard=self.COMPLETE_STANDARD)
        self.assertEqual([p for p in problems if "required" in p], [],
                         f"complete record should have no completeness problems: {problems}")

    def test_validate_equipment_optional_when_none_required(self):
        rec = self._complete_rec()                       # equipment relation omitted; status none_required
        problems = scan_fill.validate(SF_PLAN, {"322": rec}, standard=self.COMPLETE_STANDARD)
        self.assertFalse(any("relations.equipment" in p for p in problems))

    def test_validate_equipment_required_when_status_listed(self):
        rec = self._complete_rec()
        rec["scalars"]["equipment_status"] = "listed"    # claims equipment but none linked
        problems = scan_fill.validate(SF_PLAN, {"322": rec}, standard=self.COMPLETE_STANDARD)
        self.assertTrue(any("relations.equipment" in p for p in problems))

    def test_validate_contraindications_required_when_documented(self):
        rec = self._complete_rec()
        rec["scalars"]["contraindication_status"] = "documented"   # but no contraindications text
        problems = scan_fill.validate(SF_PLAN, {"322": rec}, standard=self.COMPLETE_STANDARD)
        self.assertTrue(any("contraindications" in p for p in problems))

class TestScanFillReplace(unittest.TestCase):
    def test_existing_classb_is_disconnected_not_appended(self):
        rec = json.loads(json.dumps(SF_REC))
        rec["_snapshot"] = {"linked_subrecords": {"progression_steps": ["OLDps"],
            "common_mistakes": [], "feedback_points": [], "warm_up_suggestions": [],
            "cool_down_recommendations": [], "modification_options": []}}
        rec["classb"] = {"progression_steps": rec["classb"]["progression_steps"]}  # only steps
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                 # next ps id
            rpc_result({"data": {"documentId": "NEWps1", "publishedAt": None}}),
            rpc_result({"data": {"documentId": "NEWps2", "publishedAt": None}}),
            rpc_result({"results": [{"name":"Core Stability","documentId":"tag1"}],"pagination":{"total":1}}),
            rpc_result({"results": [{"name":"Lumbar Spine","documentId":"j1"}],"pagination":{"total":1}}),
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None, "review_status":"unreviewed"}}),
        ])
        job = make_job({"kind":"scan-fill","env":"e","title":"t","batch":[322]},
                       records={"322": rec})
        c = mcp_client.McpClient("u","a",transport=ft)
        scan_fill.run(job, c, standard={"tags":["Core Stability"],"functional_goals":[],
            "exercise_target_muscle_groups":[],"modification_option_level":["Beginner"]})
        upd = [p for p in ft.sent if p.get("params",{}).get("name")=="update_exercise"][0]["params"]["arguments"]["data"]
        self.assertEqual(upd["progression_steps"],
            {"disconnect":[{"documentId":"OLDps"}], "connect":[{"documentId":"NEWps1"},{"documentId":"NEWps2"}]})

    def test_emptied_classb_field_disconnects_old_links_without_reconnect(self):
        rec = json.loads(json.dumps(SF_REC))
        rec["_snapshot"] = {"linked_subrecords": {"progression_steps": [],
            "common_mistakes": ["OLDcm"], "feedback_points": [], "warm_up_suggestions": [],
            "cool_down_recommendations": [], "modification_options": []}}
        rec["classb"] = {"progression_steps": rec["classb"]["progression_steps"]}  # common_mistakes omitted (emptied)
        ft = FakeTransport([
            rpc_result({"results": [], "pagination": {}}),                 # next ps id
            rpc_result({"data": {"documentId": "NEWps1", "publishedAt": None}}),
            rpc_result({"data": {"documentId": "NEWps2", "publishedAt": None}}),
            rpc_result({"results": [{"name":"Core Stability","documentId":"tag1"}],"pagination":{"total":1}}),
            rpc_result({"results": [{"name":"Lumbar Spine","documentId":"j1"}],"pagination":{"total":1}}),
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None, "review_status":"unreviewed"}}),
        ])
        job = make_job({"kind":"scan-fill","env":"e","title":"t","batch":[322]},
                       records={"322": rec})
        c = mcp_client.McpClient("u","a",transport=ft)
        scan_fill.run(job, c, standard={"tags":["Core Stability"],"functional_goals":[],
            "exercise_target_muscle_groups":[],"modification_option_level":["Beginner"]})
        upd = [p for p in ft.sent if p.get("params",{}).get("name")=="update_exercise"][0]["params"]["arguments"]["data"]
        self.assertEqual(upd["common_mistakes"], {"disconnect":[{"documentId":"OLDcm"}]})
        self.assertNotIn("connect", upd["common_mistakes"])
        self.assertFalse(any(p.get("params",{}).get("name")=="create_exercise-common-mistake" for p in ft.sent))

class TestScanFillRequiredFallback(unittest.TestCase):
    def test_run_fills_required_fallback_enums_when_absent(self):
        rec = {"documentId": "EX322", "scalars": {"name": "Bird Dog"}}
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None,
                                 "review_status": "unreviewed"}}),   # update exercise
        ])
        job = make_job(SF_PLAN, records={"322": rec})
        c = mcp_client.McpClient("u", "a", transport=ft)
        rc = scan_fill.run(job, c, standard={"tags": [], "functional_goals": [],
            "exercise_target_muscle_groups": [], "modification_option_level": []})
        self.assertFalse(rc)
        upd = [p for p in ft.sent if p.get("params", {}).get("name") ==
               "update_exercise"][0]["params"]["arguments"]["data"]
        self.assertEqual(upd["contraindication_status"], "unverified")
        self.assertEqual(upd["equipment_status"], "unverified")

    def test_run_does_not_clobber_existing_contraindication_status(self):
        rec = {"documentId": "EX322",
               "scalars": {"name": "Bird Dog", "contraindication_status": "none_known"}}
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None,
                                 "review_status": "unreviewed"}}),   # update exercise
        ])
        job = make_job(SF_PLAN, records={"322": rec})
        c = mcp_client.McpClient("u", "a", transport=ft)
        rc = scan_fill.run(job, c, standard={"tags": [], "functional_goals": [],
            "exercise_target_muscle_groups": [], "modification_option_level": []})
        self.assertFalse(rc)
        upd = [p for p in ft.sent if p.get("params", {}).get("name") ==
               "update_exercise"][0]["params"]["arguments"]["data"]
        self.assertEqual(upd["contraindication_status"], "none_known")    # not clobbered
        self.assertEqual(upd["equipment_status"], "unverified")           # still filled
        self.assertEqual(upd["review_status"], "unreviewed")              # still forced neutral

    def test_run_carries_name_from_existing_record_when_scalars_omit_it(self):
        # Strapi 5.47 MCP update_exercise requires the full create-required set —
        # including `name`. The record's scalars need not restate it, so the runner
        # must fetch the existing exercise and carry its name into the update payload.
        rec = {"documentId": "EX322", "scalars": {"laterality": "right"}}  # no name
        ft = FakeTransport([
            rpc_result({"data": {"documentId": "EX322", "name": "Existing Bird Dog",
                                 "carespaceId": 322, "publishedAt": None}}),  # get_exercise
            rpc_result({"data": {"documentId": "EX322", "publishedAt": None,
                                 "review_status": "unreviewed"}}),            # update_exercise
        ])
        job = make_job(SF_PLAN, records={"322": rec})
        c = mcp_client.McpClient("u", "a", transport=ft)
        rc = scan_fill.run(job, c, standard={"tags": [], "functional_goals": [],
            "exercise_target_muscle_groups": [], "modification_option_level": []})
        self.assertFalse(rc)
        names = [p.get("params", {}).get("name") for p in ft.sent]
        self.assertIn("get_exercise", names)                              # fetched the existing record
        upd = [p for p in ft.sent if p.get("params", {}).get("name") ==
               "update_exercise"][0]["params"]["arguments"]["data"]
        self.assertEqual(upd["name"], "Existing Bird Dog")               # name carried into update
        self.assertEqual(upd["carespaceId"], 322)
