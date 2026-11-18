"""publish-chain: the ONLY runner that publishes. Requires the physio's recorded
approval; publishes targets in plan order (children first — ordering is the plan
author's contract); probes availability and falls back to an admin-UI click list."""

def validate(plan, records):
    problems = []
    if not plan.get("approved_by"):
        problems.append("approved_by is required — the physio's sign-off must be recorded")
    if not plan.get("approved_at"):
        problems.append("approved_at is required")
    targets = plan.get("targets") or []
    if not targets:
        problems.append("targets must be a non-empty ordered list (children first)")
    for i, t in enumerate(targets):
        for f in ("type", "documentId"):
            if not t.get(f):
                problems.append(f"targets[{i}].{f} is required")
    return problems

def run(job, client):
    # The publish invariant lives here, not only in validate(): this runner
    # REFUSES to publish unless the physio's approval is recorded, so any direct
    # caller of run() (test, new dispatcher) is held to the same gate.
    if not (job.plan.get("approved_by") and job.plan.get("approved_at")):
        raise RuntimeError(
            "publish-chain requires recorded approval (approved_by + approved_at)")
    targets = job.plan["targets"]
    for i, t in enumerate(targets):
        key = f"publish:{i}:{t['documentId']}"
        if job.done(key):
            continue
        err, payload = client.call(f"publish_{t['type']}", {"documentId": t["documentId"]})
        if err and "disabled" in str(payload):
            job.log("MCP publish is disabled for this token. Nothing further was published.")
            job.log("Publish these in the Strapi admin, IN THIS ORDER (children first):")
            for j, tt in enumerate(targets):
                mark = "done via MCP" if job.done(f"publish:{j}:{tt['documentId']}") else "TO CLICK"
                job.log(f"  {j+1}. [{mark}] {tt['type']} {tt.get('label', '')} ({tt['documentId']})")
            return 2
        if err:
            raise RuntimeError(f"publish {t['type']} {t['documentId']}: {payload}")
        job.record(key, {"published": True})
        job.log(f"published {t['type']} {t.get('label', t['documentId'])}")
    last = targets[-1]
    err, payload = client.call(f"get_{last['type']}",
                               {"documentId": last["documentId"], "status": "published"})
    ok = (not err) and bool((client.one(payload) or {}).get("publishedAt"))
    job.log(f"verify: final target published resolves = {ok}")
    if not ok:
        raise RuntimeError("published verification failed on the final target")
