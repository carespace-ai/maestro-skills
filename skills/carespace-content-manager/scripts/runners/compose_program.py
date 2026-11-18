"""compose-program: exercises (existing) -> dosed join records -> program template.
Contract: dosing quintet all non-null on every join (dailyReps = sets*reps,
weeklyReps = dailyReps*sessions_per_week); to-many links via connect."""
import collections
from mcp_client import connect

def validate(plan, records):
    problems = []
    prog = plan.get("program") or {}
    for f in ("name", "duration", "durationType"):
        if not prog.get(f):
            problems.append(f"program.{f} is required")
    if not isinstance(plan.get("sessions_per_week"), int) or plan["sessions_per_week"] < 1:
        problems.append("sessions_per_week must be an integer >= 1")
    exercises = plan.get("exercises") or []
    if not exercises:
        problems.append("exercises must be a non-empty list")
    for i, e in enumerate(exercises):
        for f in ("carespaceId", "documentId", "sets", "reps", "order"):
            if e.get(f) in (None, ""):
                problems.append(f"exercises[{i}].{f} is required")
    orders = [e.get("order") for e in exercises if e.get("order") not in (None, "")]
    for value, count in collections.Counter(orders).items():
        if count > 1:
            problems.append(f"exercises: duplicate order value {value} — "
                             f"step keys join:<order> must be unique")
    cids = [e.get("carespaceId") for e in exercises if e.get("carespaceId") not in (None, "")]
    for value, count in collections.Counter(cids).items():
        if count > 1:
            problems.append(f"exercises: duplicate carespaceId value {value} — "
                             f"verify keys exercise:<carespaceId> must be unique")
    return problems

TAXONOMY = {"body_regions": "body-region", "joints": "joint",
            "functional_goals": "functional-goal", "reasons": "reason"}

def run(job, client):
    plan, spw = job.plan, job.plan["sessions_per_week"]
    for e in plan["exercises"]:
        key = f"exercise:{e['carespaceId']}"
        if job.done(key):
            continue
        err, payload = client.call("get_exercise", {"documentId": e["documentId"], "status": "draft"})
        if err or not client.one(payload):
            raise RuntimeError(f"exercise #{e['carespaceId']} not found: {payload}")
        job.record(key, {"documentId": e["documentId"]})
        job.log(f"verified exercise #{e['carespaceId']}")
    # Resolve every taxonomy name up front, BEFORE any write, so a bad/typo'd
    # name fails the job before a single join record is created.
    taxonomy_links = {}
    for field, uid in TAXONOMY.items():
        names = plan["program"].get(field) or []
        if names:
            taxonomy_links[field] = connect(client.resolve_names(uid, names))
    join_ids = []
    for e in plan["exercises"]:
        key = f"join:{e['order']}"
        if job.done(key):
            join_ids.append(job.state["steps"][key]["documentId"])
            continue
        cid = client.next_id("program-exercise-template")
        daily = e["sets"] * e["reps"]
        err, payload = client.call("create_program-exercise-template", {"data": {
            "carespaceId": cid,
            "name": f"{plan['program']['name']} — #{e['carespaceId']} ({e['sets']}x{e['reps']})",
            "strapiExerciseId": e["documentId"],
            "sets": e["sets"], "reps": e["reps"], "order": e["order"],
            "dailyReps": daily, "weeklyReps": daily * spw}})
        if err:
            raise RuntimeError(f"create join (order {e['order']}): {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError("join did not land as a draft — aborting")
        job.record(key, {"documentId": d["documentId"], "carespaceId": d.get("carespaceId")})
        join_ids.append(d["documentId"])
        job.log(f"join order {e['order']} -> carespaceId {d.get('carespaceId')}")
    if not job.done("program"):
        cid = client.next_id("program-template")
        data = {"carespaceId": cid, "name": plan["program"]["name"],
                "duration": plan["program"]["duration"],
                "durationType": plan["program"]["durationType"],
                "exercises": connect(join_ids)}
        data.update(taxonomy_links)
        err, payload = client.call("create_program-template", {"data": data})
        if err:
            raise RuntimeError(f"create program: {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError("program did not land as a draft — aborting")
        job.record("program", {"documentId": d["documentId"], "carespaceId": d.get("carespaceId")})
        job.log(f"program -> carespaceId {d.get('carespaceId')}")
    prog_doc = job.state["steps"]["program"]["documentId"]
    err, payload = client.call("get_program-template", {"documentId": prog_doc, "status": "draft"})
    d = client.one(payload) if not err else {}
    ex = d.get("exercises")
    n = (ex or {}).get("count") if isinstance(ex, dict) else (len(ex) if isinstance(ex, list) else 0)
    job.log(f"read-back: {n} joins linked (expected {len(join_ids)})")
    if n != len(join_ids):
        raise RuntimeError(f"read-back mismatch: {n} != {len(join_ids)}")
