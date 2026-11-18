import json, os, tempfile, unittest
import snapshot

EX_ENTITY = {  # a populated REST exercise entity (trimmed)
  "documentId":"ex1","carespaceId":42,"updatedAt":"2026-07-25T10:00:00.000Z",
  "name":"Seated Rowing","laterality":"bilateral","is_bilateral":True,
  "review_status":"approved","reviewed_by":"luis@carespace.ai","reviewed_at":"2026-07-26T06:53:00.000Z",
  "joints":[{"documentId":"j1","name":"Shoulder"},{"documentId":"j2","name":"Thoracic Spine"}],
  "tags":[{"documentId":"t1","name":"Core Stability"}],
  "exercise_target_muscle_groups":[{"documentId":"m1","name":"Rhomboids"}],
  "functional_goals":[], "body_regions":[{"documentId":"b1","name":"Upper Limb"}],
  "reasons":[{"documentId":"r1","name":"upper back pain"}], "equipment":[{"documentId":"e1","name":"chair"}],
  "exercise_positions":[{"documentId":"p1","name":"Sitting"}],
  "common_mistakes":[{"documentId":"cm1","description":"Using momentum."}],
  "feedback_points":[], "warm_up_suggestions":[], "cool_down_recommendations":[],
  "progression_steps":[{"documentId":"ps1","step":1,"description":"Light band."}],
  "modification_options":{"documentId":"mo1","description":"Seated.","level":{"documentId":"lvl1","name":"Beginner"}},
}

class TestMapExercise(unittest.TestCase):
    def test_maps_relations_to_names_and_captures_ids(self):
        rec = snapshot.map_exercise(EX_ENTITY)
        self.assertEqual(rec["documentId"], "ex1")
        self.assertEqual(rec["scalars"]["name"], "Seated Rowing")
        self.assertEqual(rec["scalars"]["review_status"], "approved")   # prescribability gate captured
        self.assertEqual(rec["scalars"]["reviewed_by"], "luis@carespace.ai")
        self.assertEqual(rec["scalars"]["reviewed_at"], "2026-07-26T06:53:00.000Z")
        self.assertEqual(rec["relations"]["joints"], ["Shoulder","Thoracic Spine"])
        self.assertEqual(rec["relations"]["equipment"], ["chair"])   # equipments -> equipment
        self.assertEqual(rec["classA"]["tags"], ["Core Stability"])
        self.assertEqual(rec["classb"]["common_mistakes"][0]["description"], "Using momentum.")
        self.assertEqual(rec["classb"]["modification_options"]["level"], "Beginner")
        self.assertEqual(rec["_snapshot"]["linked_subrecords"]["common_mistakes"], ["cm1"])
        self.assertEqual(rec["_snapshot"]["linked_subrecords"]["modification_options"], ["mo1"])
        self.assertEqual(rec["_snapshot"]["source_updatedAt"], "2026-07-25T10:00:00.000Z")

class TestWriteAndSnapshot(unittest.TestCase):
    def test_snapshot_writes_files_and_manifest(self):
        root = tempfile.mkdtemp()
        class C:
            def get_all(self, plural, extra_params=None):
                return [EX_ENTITY] if plural == "exercises" else []
        man = snapshot.snapshot(C(), root, "strapi-171", type_ids=["exercise"])
        self.assertEqual(man["counts"]["exercise"], 1)
        p = os.path.join(root, "strapi-171", "exercise", "42.json")
        self.assertTrue(os.path.exists(p))
        with open(p) as fh:
            self.assertEqual(json.load(fh)["documentId"], "ex1")
        self.assertTrue(os.path.exists(os.path.join(root, "strapi-171", "manifest.json")))

PROG_ENTITY = {"documentId":"pg1","carespaceId":9,"name":"Hip 4wk","duration":4,"durationType":"weeks",
  "body_regions":[{"name":"Lower Limb"}],"joints":[],"functional_goals":[],"reasons":[],
  "exercises":[{"documentId":"j1","order":1,"sets":2,"reps":10,"dailyReps":20,"weeklyReps":60,
                "strapiExerciseId":{"documentId":"ex7","carespaceId":7,"name":"Bridge"}}]}
CAL_ENTITY = {"documentId":"c1","carespaceId":3,"name":"Cal","weeks":1,"experienceLevel":"beginner",
  "reasons":[], "days":[{"dayNumber":1,"order":0,"activityType":"exercise",
   "exerciseProgram":{"documentId":"pg1","carespaceId":9,"name":"Hip 4wk"}}]}
SURV_ENTITY = {"documentId":"s1","carespaceId":5,"title":"S","description":"d","clinicallyValidated":False,
  "edit":False,"surveyTemplateQuestion":[{"documentId":"q1","title":"Q1","description":"d",
   "questionType":"rate","scored":True,"order":1}]}
OMNI_ENTITY = {"documentId":"o1","carespaceId":2,"title":"ROM",
  "exercises":[{"documentId":"oe1","order":1,
   "OmniRomExerciseId":{"documentId":"orx1","name":"Knee Flexion","carespaceId":7}}]}

class TestOtherMappers(unittest.TestCase):
    def test_program(self):
        r = snapshot.map_program(PROG_ENTITY)
        self.assertEqual(r["program"]["name"], "Hip 4wk")
        self.assertEqual(r["exercises"][0]["weeklyReps"], 60)
        self.assertEqual(r["exercises"][0]["exercise"]["name"], "Bridge")
    def test_calendar(self):
        r = snapshot.map_calendar(CAL_ENTITY)
        self.assertEqual(r["days"][0]["ref"]["name"], "Hip 4wk")
        self.assertEqual(r["days"][0]["activityType"], "exercise")
    def test_survey(self):
        r = snapshot.map_survey(SURV_ENTITY)
        self.assertEqual(r["questions"][0]["title"], "Q1")
        self.assertFalse(r["template"]["clinicallyValidated"])
    def test_omnirom(self):
        r = snapshot.map_omnirom(OMNI_ENTITY)
        self.assertEqual(r["exercises"][0]["OmniRomExerciseId"], "orx1")
        self.assertEqual(r["exercises"][0]["name"], "Knee Flexion")
        self.assertEqual(r["exercises"][0]["carespaceId"], 7)
        self.assertEqual(r["exercises"][0]["order"], 1)

class TestPopulateSpecs(unittest.TestCase):
    def test_exercise_spec_includes_modification_options_level(self):
        spec = snapshot.POPULATE["exercise"]
        self.assertIn("populate[modification_options][fields][0]", spec)
        self.assertIn("populate[modification_options][populate][level][fields][0]", spec)
        self.assertEqual(spec["populate[modification_options][populate][level][fields][0]"], "name")

    def test_program_spec_nests_strapi_exercise_id(self):
        spec = snapshot.POPULATE["program-template"]
        self.assertIn("populate[exercises][populate][strapiExerciseId][fields][0]", spec)

    def test_omnirom_spec_nests_omnirom_exercise_id(self):
        spec = snapshot.POPULATE["omni-rom-program"]
        self.assertIn("populate[exercises][populate][OmniRomExerciseId][fields][0]", spec)

    def test_calendar_spec_nests_day_refs(self):
        spec = snapshot.POPULATE["calendar-program-template"]
        self.assertIn("populate[days][populate][exerciseProgram][fields][0]", spec)
        self.assertIn("populate[days][populate][omniRomProgram][fields][0]", spec)
        self.assertIn("populate[days][populate][surveyTemplate][fields][0]", spec)

class TestSnapshotPassesPopulateSpec(unittest.TestCase):
    def test_snapshot_passes_program_populate_spec_to_get_all(self):
        root = tempfile.mkdtemp()
        calls = []
        class C:
            def get_all(self, plural, extra_params=None):
                calls.append((plural, extra_params))
                return [PROG_ENTITY] if plural == "program-templates" else []
        snapshot.snapshot(C(), root, "strapi-171", type_ids=["program-template"])
        self.assertEqual(len(calls), 1)
        plural, extra_params = calls[0]
        self.assertEqual(plural, "program-templates")
        self.assertIn("populate[exercises][populate][strapiExerciseId][fields][0]", extra_params)
