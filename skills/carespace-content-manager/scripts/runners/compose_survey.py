"""compose-survey: questions -> survey template. clinicallyValidated stays False
unless the plan explicitly set it (the physio's attestation happens at plan time)."""
import collections
from mcp_client import connect

def validate(plan, records):
    problems = []
    qs = plan.get("questions") or []
    if not qs:
        problems.append("questions must be a non-empty list")
    for i, q in enumerate(qs):
        for f in ("title", "description", "questionType", "order"):
            if q.get(f) in (None, ""):
                problems.append(f"questions[{i}].{f} is required")
    orders = [q.get("order") for q in qs if q.get("order") not in (None, "")]
    for value, count in collections.Counter(orders).items():
        if count > 1:
            problems.append(f"questions: duplicate order value {value} — "
                             f"step keys question:<order> must be unique")
    tpl = plan.get("template") or {}
    for f in ("title", "description"):
        if not tpl.get(f):
            problems.append(f"template.{f} is required")
    return problems

def run(job, client):
    q_ids = []
    for q in job.plan["questions"]:
        key = f"question:{q['order']}"
        if job.done(key):
            q_ids.append(job.state["steps"][key]["documentId"])
            continue
        cid = client.next_id("survey-template-question")
        err, payload = client.call("create_survey-template-question", {"data": {
            "carespaceId": cid, "title": q["title"], "description": q["description"],
            "questionType": q["questionType"], "scored": bool(q.get("scored")),
            "order": q["order"]}})
        if err:
            raise RuntimeError(f"create question {q['order']}: {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError("question did not land as a draft — aborting")
        job.record(key, {"documentId": d["documentId"]})
        q_ids.append(d["documentId"])
        job.log(f"question {q['order']} created")
    if not job.done("template"):
        tpl = job.plan["template"]
        cid = client.next_id("survey-template")
        err, payload = client.call("create_survey-template", {"data": {
            "carespaceId": cid, "title": tpl["title"], "description": tpl["description"],
            "clinicallyValidated": bool(tpl.get("clinicallyValidated")),
            "edit": bool(tpl.get("edit")),
            "surveyTemplateQuestion": connect(q_ids)}})
        if err:
            raise RuntimeError(f"create template: {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError("template did not land as a draft — aborting")
        job.record("template", {"documentId": d["documentId"], "carespaceId": d.get("carespaceId")})
        job.log("survey template created")
    tpl_doc = job.state["steps"]["template"]["documentId"]
    err, payload = client.call("get_survey-template", {"documentId": tpl_doc, "status": "draft"})
    d = client.one(payload) if not err else {}
    qs_linked = d.get("surveyTemplateQuestion")
    n = ((qs_linked or {}).get("count") if isinstance(qs_linked, dict)
         else (len(qs_linked) if isinstance(qs_linked, list) else 0))
    job.log(f"read-back: {n} questions linked (expected {len(q_ids)})")
    if n != len(q_ids):
        raise RuntimeError(f"read-back mismatch: {n} != {len(q_ids)}")
