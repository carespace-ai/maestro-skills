"""restore-snapshot: replay a captured authored-content snapshot onto this
catalog. The counterpart to capture_snapshot.py.

DRAFT-SAFE. Every write goes through `update_exercise` (the MCP document service),
which updates the DRAFT and never publishes; review_status is forced to
'unreviewed'. So restoring content never puts it live — a clinician still signs
off in the Review & publish flow. (A raw REST PUT does NOT have this property on
some deployments; that is exactly why restore goes through the MCP tools.)

MATCHING. Each snapshot record is matched to this catalog by carespaceId (the
universal cross-system key). Relations are stored by NAME and resolved to this
environment's ids; a name that is not in this catalog's canonical vocabulary is
SKIPPED and reported, never invented. Equipment is an open vocabulary, so a
referenced equipment term that is missing here is created.

IDEMPOTENT. A record whose draft already carries movement_complexity is treated as
already-authored and skipped, so a re-run resumes cleanly and a human's edits are
never clobbered. Set plan.force = true to re-apply over already-labelled drafts.
"""
import json
import os

from runners.common import REQUIRED_NEUTRAL

# The label + prose scalars a snapshot carries. name/carespaceId are the match
# key (name is carried from the target, not from the snapshot). Review/machine
# fields are never restored — REQUIRED_NEUTRAL pins review_status to unreviewed.
SCALARS = (
    "laterality", "movement_complexity", "joint_demand", "balance_demand",
    "weight_bearing", "floor_transfer_required", "requires_assistance",
    "progression_level", "contraindication_status", "equipment_status",
    "default_sets", "default_reps", "default_hold_seconds",
    "default_daily_frequency", "default_weekly_frequency",
    "contraindications", "instructions", "alignment_tips", "breathing", "precautions",
)

# snapshot key -> canonical relation type id (NEVER created here)
NAME_RELATIONS = {
    "body_regions": "body-region",
    "functional_goals": "functional-goal",
    "tags": "exercise-tag",
}
EQUIP_KEY = "equipment"          # open vocabulary — missing terms are created


def _snapshot_path(job):
    p = job.plan.get("snapshot")
    if not p:
        raise RuntimeError("plan.snapshot (path to the snapshot json) is required")
    return p if os.path.isabs(p) else os.path.join(job.dir, p)


def _load_snapshot(job):
    with open(_snapshot_path(job)) as fh:
        return json.load(fh)


def _index_by_name(client, uid):
    """name(lower) -> documentId over all draft rows of a vocabulary type."""
    idx, page = {}, 1
    while True:
        err, payload = client.call(f"list_{uid}", {"status": "draft", "pageSize": 100, "page": page})
        if err:
            raise RuntimeError(f"list_{uid}: {payload}")
        rows = client.rows(payload)
        for x in rows:
            if x.get("name"):
                idx[str(x["name"]).strip().lower()] = x.get("documentId")
        if len(rows) < 100:
            break
        page += 1
    return idx


def validate(plan, records, standard=None):
    problems = []
    if not plan.get("snapshot"):
        problems.append("plan.snapshot (path to the snapshot json) is required")
    return problems


def run(job, client, standard=None):
    snap = _load_snapshot(job)
    exercises = snap.get("exercises", [])
    force = bool(job.plan.get("force"))

    # carespaceId -> (documentId, movement_complexity, name) over this catalog.
    exidx, page = {}, 1
    while True:
        err, payload = client.call("list_exercise", {"status": "draft", "pageSize": 100, "page": page})
        if err:
            raise RuntimeError(f"list_exercise: {payload}")
        rows = client.rows(payload)
        for x in rows:
            if x.get("carespaceId") is not None:
                exidx[x["carespaceId"]] = (x.get("documentId"), x.get("movement_complexity"), x.get("name"))
        if len(rows) < 100:
            break
        page += 1

    relidx = {key: _index_by_name(client, uid) for key, uid in NAME_RELATIONS.items()}
    equipidx = _index_by_name(client, "equipment")

    # Create any referenced equipment term missing here (open vocabulary).
    referenced = {e for ex in exercises for e in (ex.get(EQUIP_KEY) or [])}
    for name in sorted(referenced):
        if str(name).strip().lower() in equipidx:
            continue
        nid = client.next_id("equipment")
        err, payload = client.call("create_equipment", {"data": {"name": name, "carespaceId": nid}})
        if err:
            raise RuntimeError(f"create_equipment {name!r}: {payload}")
        equipidx[str(name).strip().lower()] = client.one(payload)["documentId"]
        job.log(f"equipment created: {name}")

    def resolve(idx, names, kind, missing):
        out = []
        for n in names or []:
            did = idx.get(str(n).strip().lower())
            if did:
                out.append({"documentId": did})
            else:
                missing.append(f"{kind}:{n}")
        return out

    counts = {"restored": 0, "skipped_already": 0, "not_found": 0, "with_unresolved": 0}
    for e in exercises:
        cid = e.get("carespaceId")
        key = f"restore:{cid}"
        if job.done(key):
            continue
        tgt = exidx.get(cid)
        if not tgt:
            counts["not_found"] += 1
            job.record(key, {"skipped": "not_found"})
            job.log(f"#{cid} not found in this catalog — skipped")
            continue
        did, mc, name = tgt
        if mc and not force:
            counts["skipped_already"] += 1
            job.record(key, {"skipped": "already_labelled"})
            continue

        missing = []
        data = {"name": name, "carespaceId": cid, **REQUIRED_NEUTRAL}
        for f in SCALARS:
            if e.get(f) is not None:
                data[f] = e[f]
        for rkey, uid in NAME_RELATIONS.items():
            data[rkey] = {"set": resolve(relidx[rkey], e.get(rkey), uid, missing)}
        data[EQUIP_KEY] = {"set": resolve(equipidx, e.get(EQUIP_KEY), "equipment", missing)}

        err, payload = client.call("update_exercise", {"documentId": did, "data": data})
        if err:
            raise RuntimeError(f"#{cid} update_exercise: {payload}")
        d = client.one(payload)
        if d.get("publishedAt") is not None:
            raise RuntimeError(f"#{cid}: restore unexpectedly published a record — aborting")

        counts["restored"] += 1
        if missing:
            counts["with_unresolved"] += 1
        job.record(key, {"documentId": did, "unresolved": missing})
        job.log(f"#{cid} restored (draft, unreviewed)" + (f"  unresolved={missing}" if missing else ""))

    job.log(f"restore-snapshot done: {counts}")
    return 0
