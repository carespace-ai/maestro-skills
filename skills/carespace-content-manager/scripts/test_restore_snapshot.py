import json, os, tempfile, unittest
from runners import restore_snapshot
from runners.common import Job


def make_job(snapshot, force=False):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "snapshot.json"), "w") as fh:
        json.dump(snapshot, fh)
    with open(os.path.join(d, "plan.json"), "w") as fh:
        json.dump({"kind": "restore-snapshot", "env": "e", "snapshot": "./snapshot.json", "force": force}, fh)
    os.makedirs(os.path.join(d, "records"))
    return Job(d)


class FakeClient:
    """Minimal MCP-client stand-in: canned list_* reads, captured writes."""
    def __init__(self, exercises, vocab):
        self.exercises = exercises            # [{carespaceId, documentId, movement_complexity, name}]
        self.vocab = {k: list(v) for k, v in vocab.items()}   # {uid: [{name, documentId}]}
        self.updates = []
        self.creates = []

    def call(self, tool, args):
        if tool == "list_exercise":
            page, per = args["page"], args["pageSize"]
            return None, {"results": self.exercises[(page - 1) * per: page * per], "pagination": {}}
        if tool.startswith("list_"):
            rows = self.vocab.get(tool[len("list_"):], [])
            page, per = args["page"], args["pageSize"]
            return None, {"results": rows[(page - 1) * per: page * per], "pagination": {}}
        if tool == "create_equipment":
            did = f"eq-{len(self.creates)}"
            self.creates.append(args["data"]["name"])
            self.vocab.setdefault("equipment", []).append({"name": args["data"]["name"], "documentId": did})
            return None, {"data": {"documentId": did}}
        if tool == "update_exercise":
            self.updates.append(args)
            return None, {"data": {"documentId": args["documentId"], "publishedAt": None}}
        raise AssertionError(f"unexpected tool {tool}")

    def rows(self, payload):
        return payload.get("results", [])

    def one(self, payload):
        return payload.get("data", {})

    def next_id(self, uid):
        return 1


SNAP = {"exercises": [
    {"carespaceId": 1, "name": "A", "movement_complexity": "simple", "laterality": "left",
     "instructions": "do the thing", "equipment_status": "listed",
     "body_regions": ["Hip", "Nonexistent"], "functional_goals": [], "tags": ["Mobility"],
     "equipment": ["dumbbell"]},
    {"carespaceId": 2, "name": "B", "movement_complexity": "moderate",
     "body_regions": ["Hip"], "functional_goals": [], "tags": [], "equipment": []},
    {"carespaceId": 99, "name": "Gone", "movement_complexity": "simple",
     "body_regions": [], "functional_goals": [], "tags": [], "equipment": []},
]}

CATALOG = [
    {"carespaceId": 1, "documentId": "d1", "movement_complexity": None, "name": "A"},
    {"carespaceId": 2, "documentId": "d2", "movement_complexity": "moderate", "name": "B"},  # already labelled
]
VOCAB = {
    "body-region": [{"name": "Hip", "documentId": "br-hip"}],
    "functional-goal": [],
    "exercise-tag": [{"name": "Mobility", "documentId": "t-mob"}],
    "equipment": [],  # dumbbell missing -> must be created
}


class TestRestoreSnapshot(unittest.TestCase):
    def test_validate_requires_snapshot(self):
        self.assertTrue(any("snapshot" in p for p in restore_snapshot.validate({}, {})))
        self.assertEqual(restore_snapshot.validate({"snapshot": "x"}, {}), [])

    def test_restore_writes_drafts_resolves_names_and_is_idempotent(self):
        job = make_job(SNAP)
        c = FakeClient(list(CATALOG), VOCAB)
        rc = restore_snapshot.run(job, c)
        self.assertFalse(rc)

        # Only cid=1 is written (cid=2 already labelled -> skipped; cid=99 not in catalog).
        self.assertEqual(len(c.updates), 1)
        upd = c.updates[0]
        self.assertEqual(upd["documentId"], "d1")
        d = upd["data"]
        # never publishes / never approves
        self.assertEqual(d["review_status"], "unreviewed")
        # name + carespaceId carried (required-set)
        self.assertEqual(d["name"], "A")
        self.assertEqual(d["carespaceId"], 1)
        # scalars applied
        self.assertEqual(d["movement_complexity"], "simple")
        # relations resolved by name; the unknown "Nonexistent" is dropped, "Hip" kept
        self.assertEqual(d["body_regions"], {"set": [{"documentId": "br-hip"}]})
        self.assertEqual(d["tags"], {"set": [{"documentId": "t-mob"}]})
        # missing equipment vocab created, then linked
        self.assertEqual(c.creates, ["dumbbell"])
        self.assertEqual(d["equipment"], {"set": [{"documentId": "eq-0"}]})
        # the dropped relation is recorded on the step for the physio
        self.assertIn("body-region:Nonexistent", job.state["steps"]["restore:1"]["unresolved"])

        # Re-run is a no-op (idempotent via state.json).
        c2 = FakeClient(list(CATALOG), VOCAB)
        restore_snapshot.run(job, c2)
        self.assertEqual(len(c2.updates), 0)

    def test_force_reapplies_over_labelled(self):
        job = make_job(SNAP, force=True)
        c = FakeClient(list(CATALOG), VOCAB)
        restore_snapshot.run(job, c)
        # with force, the already-labelled cid=2 is also written
        self.assertEqual({u["documentId"] for u in c.updates}, {"d1", "d2"})


if __name__ == "__main__":
    unittest.main()
