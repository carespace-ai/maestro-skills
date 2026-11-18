import json, os, tempfile, unittest
import mirror_to_job

MIRROR = {"documentId":"ex1","carespaceId":42,
  "scalars":{"name":"X","is_bilateral":True,"laterality":"bilateral","contraindication_status":"unverified",
             "equipment_status":"listed"},
  "relations":{"joints":["Shoulder"]}, "classA":{"tags":["Core Stability"]},
  "classb":{"progression_steps":[{"step":1,"description":"a"}]},
  "_snapshot":{"documentId":"ex1","source_updatedAt":"2026-07-25T10:00:00.000Z",
               "linked_subrecords":{"progression_steps":["OLDps"]}}}

class TestWritable(unittest.TestCase):
    def test_drops_derived_scalars_keeps_rest(self):
        jr = mirror_to_job.writable_record(MIRROR)
        self.assertNotIn("is_bilateral", jr["scalars"])
        self.assertEqual(jr["scalars"]["laterality"], "bilateral")
        self.assertEqual(jr["relations"]["joints"], ["Shoulder"])
        self.assertEqual(jr["_snapshot"]["linked_subrecords"]["progression_steps"], ["OLDps"])
    def test_does_not_mutate_input(self):
        _ = mirror_to_job.writable_record(MIRROR)
        self.assertIn("is_bilateral", MIRROR["scalars"])   # original untouched
    def test_drops_none_valued_scalars(self):
        rec = {"documentId":"ex2","carespaceId":43,
          "scalars":{"name":"Gap Ex","is_bilateral":True,"laterality":"bilateral",
                     "joint_demand":None,"balance_demand":"low"},
          "relations":{}, "classA":{}, "classb":{},
          "_snapshot":{"documentId":"ex2","source_updatedAt":"2026-07-25T10:00:00.000Z"}}
        jr = mirror_to_job.writable_record(rec)
        self.assertNotIn("joint_demand", jr["scalars"])
        self.assertNotIn("is_bilateral", jr["scalars"])
        self.assertEqual(jr["scalars"]["laterality"], "bilateral")
        self.assertEqual(jr["scalars"]["balance_demand"], "low")

class TestDrift(unittest.TestCase):
    def test_flags_changed_updatedAt(self):
        class RC:
            def get_one(self, plural, doc): return {"updatedAt":"2026-07-26T00:00:00.000Z"}
        self.assertIsNotNone(mirror_to_job.check_drift(RC(), "exercises", MIRROR))
    def test_none_when_unchanged(self):
        class RC:
            def get_one(self, plural, doc): return {"updatedAt":"2026-07-25T10:00:00.000Z"}
        self.assertIsNone(mirror_to_job.check_drift(RC(), "exercises", MIRROR))
    def test_flags_deleted(self):
        class RC:
            def get_one(self, plural, doc): return None
        self.assertIsNotNone(mirror_to_job.check_drift(RC(), "exercises", MIRROR))

class TestBuildJob(unittest.TestCase):
    def test_writes_plan_and_record(self):
        d = tempfile.mkdtemp()
        mirror_to_job.build_job(MIRROR, d)
        with open(os.path.join(d, "plan.json")) as fh:
            plan = json.load(fh)
        self.assertEqual(plan["kind"], "scan-fill")
        self.assertEqual(plan["batch"], [42])
        with open(os.path.join(d, "records", "42.json")) as fh:
            rec = json.load(fh)
        self.assertNotIn("is_bilateral", rec["scalars"])   # writable subset persisted
