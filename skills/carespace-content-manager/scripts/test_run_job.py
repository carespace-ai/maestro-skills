import json, os, shutil, tempfile, unittest
import run_job
from runners.common import Job

class TestWorkspaceInit(unittest.TestCase):
    def test_init_scaffolds_claude_progress_git_once(self):
        root = tempfile.mkdtemp()
        run_job.init_workspace(root)
        self.assertTrue(os.path.isdir(os.path.join(root, ".git")))
        with open(os.path.join(root, "CLAUDE.md")) as fh:
            claude = fh.read()
        self.assertIn("routing", claude.lower())
        self.assertLessEqual(len(claude.splitlines()), 50)
        self.assertTrue(os.path.exists(os.path.join(root, "PROGRESS.md")))
        # re-init must not overwrite
        with open(os.path.join(root, "PROGRESS.md"), "a") as fh:
            fh.write("MARKER\n")
        run_job.init_workspace(root)
        with open(os.path.join(root, "PROGRESS.md")) as fh:
            self.assertIn("MARKER", fh.read())
        shutil.rmtree(root)

class TestJobLoading(unittest.TestCase):
    def make_job(self, plan):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "plan.json"), "w") as fh:
            json.dump(plan, fh)
        os.makedirs(os.path.join(d, "records"), exist_ok=True)
        return d

    def test_unknown_kind_fails_before_network(self):
        d = self.make_job({"kind": "nope", "env": "strapi-x", "title": "t"})
        rc = run_job.main([d])
        self.assertEqual(rc, 1)

    def test_state_roundtrip_and_resume_keys(self):
        d = self.make_job({"kind": "compose-survey", "env": "e", "title": "t",
                           "questions": [], "template": {}})
        job = Job(d)
        self.assertFalse(job.done("q:1"))
        job.record("q:1", {"documentId": "x"})
        job2 = Job(d)                        # fresh load reads persisted state
        self.assertTrue(job2.done("q:1"))
        self.assertEqual(job2.state["steps"]["q:1"]["documentId"], "x")

    def test_records_loaded_by_stem(self):
        d = self.make_job({"kind": "scan-fill", "env": "e", "title": "t", "batch": [322]})
        with open(os.path.join(d, "records", "322.json"), "w") as fh:
            json.dump({"scalars": {"name": "X"}}, fh)
        job = Job(d)
        self.assertIn("322", job.records)
