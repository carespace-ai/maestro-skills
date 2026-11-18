"""compose-calendar: inline day components, activityType-gated relations only.
Backend date math depends on weeks 1-52, dayNumber >= 1, order >= 0."""
GATES = {"exercise": ("exerciseProgram", "exerciseItems"),
         "omniRom": ("omniRomProgram", "omniRomExercises"),
         "survey": ("surveyTemplate", None),
         "evaluation": (None, None), "posture": (None, None), "bodyComposition": (None, None)}
_EXPECT = {"exercise": "program-template", "omniRom": "omni-rom-program", "survey": "survey-template"}

def validate(plan, records):
    problems = []
    tpl = plan.get("template") or {}
    if not tpl.get("name"):
        problems.append("template.name is required")
    if not isinstance(tpl.get("weeks"), int) or not 1 <= tpl["weeks"] <= 52:
        problems.append("template.weeks must be an integer 1-52")
    if not tpl.get("experienceLevel"):
        problems.append("template.experienceLevel is required")
    for i, day in enumerate(plan.get("days") or []):
        at = day.get("activityType")
        if at not in GATES:
            problems.append(f"days[{i}].activityType '{at}' invalid")
            continue
        if not isinstance(day.get("dayNumber"), int) or day["dayNumber"] < 1:
            problems.append(f"days[{i}].dayNumber must be >= 1")
        if not isinstance(day.get("order"), int) or day["order"] < 0:
            problems.append(f"days[{i}].order must be >= 0")
        rel, _ = GATES[at]
        ref = day.get("ref")
        if rel and not (ref and ref.get("documentId")):
            problems.append(f"days[{i}]: activityType '{at}' requires ref.documentId")
        if not rel and ref:
            problems.append(f"days[{i}]: activityType '{at}' gates no relation but ref present")
        if rel and ref and _EXPECT[at] != ref.get("type"):
            problems.append(f"days[{i}]: ref.type must be {_EXPECT[at]} for '{at}'")
    if not plan.get("days"):
        problems.append("days must be a non-empty list")
    return problems

def run(job, client):
    plan = job.plan
    if not job.done("calendar"):
        days = []
        for day in plan["days"]:
            d = {"dayNumber": day["dayNumber"], "order": day["order"],
                 "activityType": day["activityType"]}
            rel, _sub = GATES[day["activityType"]]
            if rel:
                d[rel] = day["ref"]["documentId"]
            days.append(d)
        cid = client.next_id("calendar-program-template")
        data = {"carespaceId": cid, "name": plan["template"]["name"],
                "weeks": plan["template"]["weeks"],
                "experienceLevel": plan["template"]["experienceLevel"], "days": days}
        err, payload = client.call("create_calendar-program-template", {"data": data})
        if err:
            raise RuntimeError(f"create calendar: {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError("calendar did not land as a draft")
        job.record("calendar", {"documentId": d["documentId"], "carespaceId": d.get("carespaceId")})
        job.log(f"calendar -> carespaceId {d.get('carespaceId')}")
    doc = job.state["steps"]["calendar"]["documentId"]
    err, payload = client.call("get_calendar-program-template",
        {"documentId": doc, "status": "draft", "populate": "*"})
    rb_days = (client.one(payload) or {}).get("days") or [] if not err else []
    got = len(rb_days)
    job.log(f"read-back: {got} days (expected {len(job.plan['days'])})")
    if got != len(job.plan["days"]):
        raise RuntimeError("day round-trip mismatch")
    # Keyed by (dayNumber, order), not dayNumber alone: a day legitimately holds
    # several activities (assessment + survey + exercise on day 1), and collapsing
    # them by day would check each plan entry against whichever component happened
    # to come last — failing a correct write.
    by_key = {(d.get("dayNumber"), d.get("order")): d for d in rb_days}
    for day in job.plan["days"]:
        rel, _sub = GATES[day["activityType"]]
        if not rel:
            continue
        comp = by_key.get((day["dayNumber"], day["order"])) or {}
        if not _present(comp.get(rel)):
            raise RuntimeError(
                f"day {day['dayNumber']} (order {day['order']}): "
                f"gated relation '{rel}' did not persist")

def _present(val):
    """A gated x-to-one reads back as {'count':1} / a linked object / a documentId
    string; an absent one is None, missing, or {'count':0}."""
    if isinstance(val, dict):
        return val.get("count", 1) >= 1 if "count" in val else bool(val)
    if isinstance(val, list):
        return len(val) > 0
    return bool(val)
