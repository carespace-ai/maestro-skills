"""Shared job/workspace machinery for the content-manager runners."""
import datetime, json, os, tempfile

REQUIRED_NEUTRAL = {"review_status": "unreviewed"}

# Required enums that must be PRESENT on an exercise update but, unlike the review-state
# fields, must NOT be clobbered when the record already carries a real value. "unverified"
# is the non-affirming neutral for both (an affirmative clearance is only set in review).
REQUIRED_FALLBACK = {"contraindication_status": "unverified", "equipment_status": "unverified"}

def _skill_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_standard(path=None):
    path = path or os.path.join(_skill_root(), "..", "references", "controlled-vocabularies.json")
    with open(path) as fh:
        return json.load(fh)

class Job:
    def __init__(self, job_dir):
        self.dir = os.path.abspath(job_dir)
        with open(os.path.join(self.dir, "plan.json")) as fh:
            self.plan = json.load(fh)
        self.records = {}
        rec_dir = os.path.join(self.dir, "records")
        if os.path.isdir(rec_dir):
            for fn in sorted(os.listdir(rec_dir)):
                if fn.endswith(".json"):
                    with open(os.path.join(rec_dir, fn)) as fh:
                        self.records[fn[:-5]] = json.load(fh)
        self._state_path = os.path.join(self.dir, "state.json")
        if os.path.exists(self._state_path):
            with open(self._state_path) as fh:
                self.state = json.load(fh)
        else:
            self.state = {"steps": {}}

    def done(self, key):
        return key in self.state["steps"]

    def record(self, key, value):
        self.state["steps"][key] = value
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".state-")
        with os.fdopen(fd, "w") as fh:
            json.dump(self.state, fh, indent=1)
        os.replace(tmp, self._state_path)

    def log(self, msg):
        line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line)
        with open(os.path.join(self.dir, "log.txt"), "a") as fh:
            fh.write(line + "\n")
