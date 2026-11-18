"""scan-fill: apply reconciled research-agent outputs (records/<cid>.json) to
existing exercises. Claude does the scanning/research/reconciliation; this runner
does only the deterministic writes. Never sets an approving review value."""
from mcp_client import connect
from runners.common import REQUIRED_NEUTRAL, REQUIRED_FALLBACK, load_standard

def _replace_or_connect(new_ids, old_ids):
    payload = {"connect": [{"documentId": d} for d in new_ids]}
    if old_ids:
        payload["disconnect"] = [{"documentId": d} for d in old_ids]
    return payload

CLASSA = {"tags": ("exercise-tag", "tags"),
          "functional_goals": ("functional-goal", "functional_goals"),
          "exercise_target_muscle_groups": ("exercise-target-muscle-group",
                                            "exercise_target_muscle_groups")}
RELATIONS = {"exercise_positions": "exercise-position", "joints": "joint",
             "body_regions": "body-region", "reasons": "reason", "equipment": "equipment"}
CLASSB = {"common_mistakes": ("exercise-common-mistake", ("description",)),
          "feedback_points": ("exercise-feedback-point", ("description",)),
          "warm_up_suggestions": ("exercise-warm-up-suggestion", ("description", "duration")),
          "cool_down_recommendations": ("exercise-cool-down-recommendation",
                                        ("description", "duration")),
          "progression_steps": ("exercise-progression-step", ("step", "description"))}

# Completeness gate — the AI-readiness field set scan-fill must fill on EVERY record.
# Media, CV/scoring (orientation, pointsTo*), review/machine fields, and `name` (fetched
# from the live record by run()) are intentionally NOT gated. Softer prose fields
# (alignment_tips, breathing, precautions, functional_applications, supportive_surfaces,
# contraindication_tags) are left ungated — the research agent still fills them, but a
# missing one does not block the write.
REQUIRED_SCALARS = ("laterality", "movement_complexity", "joint_demand", "balance_demand",
                    "progression_level", "weight_bearing", "floor_transfer_required",
                    "requires_assistance", "equipment_status", "contraindication_status",
                    "default_sets", "default_reps", "default_hold_seconds",
                    "default_daily_frequency", "default_weekly_frequency",
                    "instructions", "description")
REQUIRED_RELATIONS = ("exercise_positions", "joints", "body_regions", "reasons")
REQUIRED_CLASSA = ("tags", "functional_goals", "exercise_target_muscle_groups")
REQUIRED_CLASSB = ("common_mistakes", "feedback_points", "warm_up_suggestions",
                   "cool_down_recommendations", "progression_steps")

def _empty(v):
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False  # numbers and booleans (including False and 0) count as filled

def _completeness_problems(cid, rec):
    """Every FILL-THESE field must be present, or scan-fill would write a partial
    record — which defeats the whole point of scan & fill. Relations are gated
    smartly: equipment is optional when equipment_status=none_required, and the
    contraindications text is required only when the status claims 'documented'."""
    probs, sc = [], (rec.get("scalars") or {})
    rel, ca, cb = (rec.get("relations") or {}), (rec.get("classA") or {}), (rec.get("classb") or {})
    for f in REQUIRED_SCALARS:
        if _empty(sc.get(f)):
            probs.append(f"{cid}: scalars.{f} is required (scan-fill must fill every field)")
    if str(sc.get("equipment_status", "")).strip().lower() != "none_required" and _empty(rel.get("equipment")):
        probs.append(f"{cid}: relations.equipment is required (or set equipment_status=none_required)")
    for f in REQUIRED_RELATIONS:
        if _empty(rel.get(f)):
            probs.append(f"{cid}: relations.{f} is required")
    for f in REQUIRED_CLASSA:
        if _empty(ca.get(f)):
            probs.append(f"{cid}: classA.{f} is required")
    for f in REQUIRED_CLASSB:
        if _empty(cb.get(f)):
            probs.append(f"{cid}: classb.{f} is required")
    if _empty(cb.get("modification_options")):
        probs.append(f"{cid}: classb.modification_options is required")
    if str(sc.get("contraindication_status", "")).strip().lower() == "documented" and _empty(sc.get("contraindications")):
        probs.append(f"{cid}: scalars.contraindications text is required when contraindication_status=documented")
    return probs

def validate(plan, records, standard=None):
    standard = standard or load_standard()
    problems = []
    for cid in plan.get("batch") or []:
        rec = records.get(str(cid))
        if rec is None:
            problems.append(f"records/{cid}.json missing for batch entry {cid}")
            continue
        if not rec.get("documentId"):
            problems.append(f"records/{cid}.json: documentId is required")
        problems.extend(_completeness_problems(cid, rec))
        for field, (_uid, std_key) in CLASSA.items():
            canon = {t.strip().lower() for t in standard.get(std_key, [])}
            for name in (rec.get("classA") or {}).get(field) or []:
                if name.strip().lower() not in canon:
                    problems.append(f"{cid}: classA.{field} '{name}' is not canonical")
        mo = (rec.get("classb") or {}).get("modification_options")
        if mo:
            levels = {t.strip().lower() for t in standard.get("modification_option_level", [])}
            if str(mo.get("level", "")).strip().lower() not in levels:
                problems.append(f"{cid}: modification_options.level must be canonical")
            if not str(mo.get("description", "")).strip():
                problems.append(f"{cid}: modification_options.description is required")
    if not plan.get("batch"):
        problems.append("batch must be a non-empty list")
    return problems

def run(job, client, standard=None):
    standard = standard or load_standard()
    for cid in job.plan["batch"]:
        rec = job.records[str(cid)]
        linked = (rec.get("_snapshot") or {}).get("linked_subrecords") or {}
        links = {}
        for field, (uid, fields) in CLASSB.items():
            items = (rec.get("classb") or {}).get(field) or []
            if field == "progression_steps":
                items = sorted(items, key=lambda x: x.get("step") or 0)
            ids = []
            next_cid = None
            for i, it in enumerate(items):
                key = f"{cid}:{field}:{i}"
                if job.done(key):
                    ids.append(job.state["steps"][key]["documentId"])
                    continue
                data = {k: it[k] for k in fields if k in it}
                if next_cid is None:
                    next_cid = client.next_id(uid)
                data["carespaceId"] = next_cid
                next_cid += 1
                err, payload = client.call(f"create_{uid}", {"data": data})
                if err:
                    raise RuntimeError(f"{cid} {field}[{i}]: {payload}")
                d = client.one(payload)
                if d.get("publishedAt") is not None:
                    raise RuntimeError(f"{cid} {field}[{i}]: create did not stay a draft")
                job.record(key, {"documentId": d["documentId"]})
                ids.append(d["documentId"])
            old = linked.get(field, [])
            if ids:
                links[field] = _replace_or_connect(ids, old)
            elif old:
                links[field] = {"disconnect": [{"documentId": d} for d in old]}
        mo = (rec.get("classb") or {}).get("modification_options")
        if mo:
            key = f"{cid}:modification_options"
            if not job.done(key):
                mid = client.next_id("exercise-modification-option")
                err, payload = client.call("create_exercise-modification-option",
                    {"data": {"description": mo["description"], "carespaceId": mid}})
                if err:
                    raise RuntimeError(f"{cid} modification: {payload}")
                d = client.one(payload)
                if d.get("publishedAt") is not None:
                    raise RuntimeError(f"{cid} modification: create did not stay a draft")
                lvl = client.resolve_names("exercise-modification-option-level", [mo["level"]])[0]
                err, payload = client.call("update_exercise-modification-option",
                    {"documentId": d["documentId"],
                     "data": {"carespaceId": mid, "description": mo["description"], "level": lvl}})
                if err:
                    raise RuntimeError(f"{cid} modification level: {payload}")
                job.record(key, {"documentId": d["documentId"]})
            links["modification_options"] = job.state["steps"][key]["documentId"]
        key = f"{cid}:update"
        if not job.done(key):
            data = dict(rec.get("scalars") or {})
            data["carespaceId"] = cid
            # Strapi 5.47 MCP update_exercise re-validates the full create-required
            # set (name + carespaceId + the review enums), so `name` must be present
            # even on an edit. The record's scalars need not restate it — fetch the
            # existing exercise and carry its name forward when the record omits it.
            if "name" not in data:
                err, payload = client.call("get_exercise",
                    {"documentId": rec["documentId"]})
                if err:
                    raise RuntimeError(f"{cid} get_exercise: {payload}")
                data["name"] = client.one(payload)["name"]
            for k, v in REQUIRED_FALLBACK.items():
                data.setdefault(k, v)     # fill only if the record didn't supply it
            data.update(REQUIRED_NEUTRAL) # review-state always forced neutral
            for field, (uid, _std) in CLASSA.items():
                names = (rec.get("classA") or {}).get(field)
                if names:
                    data[field] = connect(client.resolve_names(uid, names))
            for field, uid in RELATIONS.items():
                names = (rec.get("relations") or {}).get(field)
                if names:
                    data[field] = connect(client.resolve_names(uid, names))
            data.update(links)
            err, payload = client.call("update_exercise",
                {"documentId": rec["documentId"], "data": data})
            if err:
                raise RuntimeError(f"{cid} update_exercise: {payload}")
            d = client.one(payload)
            if d.get("publishedAt") is not None:
                raise RuntimeError(f"{cid}: update did not stay a draft")
            job.record(key, {"documentId": rec["documentId"]})
        job.log(f"#{cid} filled (draft, unreviewed)")
