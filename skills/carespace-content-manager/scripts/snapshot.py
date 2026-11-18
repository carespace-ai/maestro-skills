#!/usr/bin/env python3
"""Snapshot the Strapi catalog to local JSON files in runner-record format.
Download is REST-only (see rest_client). Relations are rendered as NAMES; existing
sub-record ids are captured under _snapshot.linked_subrecords for replace-on-write."""
import argparse, json, os, tempfile
import rest_client

def names(rel):
    if isinstance(rel, list):
        return [x.get("name") or x.get("title") for x in rel if isinstance(x, dict)]
    return []

def _ids(rel):
    if isinstance(rel, list):
        return [x.get("documentId") for x in rel if isinstance(x, dict)]
    if isinstance(rel, dict) and rel.get("documentId"):
        return [rel["documentId"]]
    return []

_EX_SCALARS = ("name","review_status","reviewed_by","reviewed_at",
    "contraindication_status","equipment_status","laterality","is_bilateral",
    "movement_complexity","joint_demand","balance_demand","weight_bearing","floor_transfer_required",
    "requires_assistance","progression_level","default_sets","default_reps","default_hold_seconds",
    "default_daily_frequency","default_weekly_frequency","description","instructions","contraindications",
    "contraindication_tags","alignment_tips","breathing","precautions","functional_applications",
    "supportive_surfaces","equipment_alternatives")
_EX_CLASSB = ("common_mistakes","feedback_points","warm_up_suggestions","cool_down_recommendations",
    "progression_steps")

def map_exercise(e):
    classb = {}
    for f in _EX_CLASSB:
        items = e.get(f) or []
        keep = ("step","description","duration")
        classb[f] = [{k: it[k] for k in keep if k in it} for it in items]
    mo = e.get("modification_options")
    if isinstance(mo, dict) and mo:
        lvl = mo.get("level")
        classb["modification_options"] = {"description": mo.get("description"),
            "level": (lvl.get("name") if isinstance(lvl, dict) else None)}
    linked = {f: _ids(e.get(f)) for f in _EX_CLASSB}
    linked["modification_options"] = _ids(e.get("modification_options"))
    return {
        "documentId": e.get("documentId"),
        "scalars": {k: e[k] for k in _EX_SCALARS if k in e},
        "relations": {"exercise_positions": names(e.get("exercise_positions")),
            "joints": names(e.get("joints")), "body_regions": names(e.get("body_regions")),
            "reasons": names(e.get("reasons")), "equipment": names(e.get("equipment"))},
        "classA": {"tags": names(e.get("tags")),
            "functional_goals": names(e.get("functional_goals")),
            "exercise_target_muscle_groups": names(e.get("exercise_target_muscle_groups"))},
        "classb": classb,
        "_snapshot": {"documentId": e.get("documentId"),
            "source_updatedAt": e.get("updatedAt"), "linked_subrecords": linked},
    }

_GATE_REL = {"exercise":"exerciseProgram","omniRom":"omniRomProgram","survey":"surveyTemplate"}

def map_program(e):
    joins = []
    for j in e.get("exercises") or []:
        ex = j.get("strapiExerciseId") or {}
        joins.append({"exercise": {"documentId": ex.get("documentId"),
            "carespaceId": ex.get("carespaceId"), "name": ex.get("name")},
            "order": j.get("order"), "sets": j.get("sets"), "reps": j.get("reps"),
            "dailyReps": j.get("dailyReps"), "weeklyReps": j.get("weeklyReps")})
    return {"documentId": e.get("documentId"),
        "program": {"name": e.get("name"), "duration": e.get("duration"),
            "durationType": e.get("durationType"), "body_regions": names(e.get("body_regions")),
            "joints": names(e.get("joints")), "functional_goals": names(e.get("functional_goals")),
            "reasons": names(e.get("reasons"))},
        "exercises": joins,
        "_snapshot": {"documentId": e.get("documentId"), "source_updatedAt": e.get("updatedAt")}}

def map_calendar(e):
    days = []
    for d in e.get("days") or []:
        at = d.get("activityType"); rel = _GATE_REL.get(at); ref = None
        if rel and isinstance(d.get(rel), dict):
            r = d[rel]; ref = {"documentId": r.get("documentId"),
                "carespaceId": r.get("carespaceId"), "name": r.get("name") or r.get("title")}
        days.append({"dayNumber": d.get("dayNumber"), "order": d.get("order"),
            "activityType": at, "ref": ref})
    return {"documentId": e.get("documentId"),
        "template": {"name": e.get("name"), "weeks": e.get("weeks"),
            "experienceLevel": e.get("experienceLevel"), "reasons": names(e.get("reasons"))},
        "days": days,
        "_snapshot": {"documentId": e.get("documentId"), "source_updatedAt": e.get("updatedAt")}}

def map_survey(e):
    qs = [{"title": q.get("title"), "description": q.get("description"),
           "questionType": q.get("questionType"), "scored": q.get("scored"), "order": q.get("order")}
          for q in e.get("surveyTemplateQuestion") or []]
    return {"documentId": e.get("documentId"),
        "template": {"title": e.get("title"), "description": e.get("description"),
            "clinicallyValidated": e.get("clinicallyValidated"), "edit": e.get("edit")},
        "questions": qs,
        "_snapshot": {"documentId": e.get("documentId"), "source_updatedAt": e.get("updatedAt")}}

def map_omnirom(e):
    exs = [{"OmniRomExerciseId": (j.get("OmniRomExerciseId") or {}).get("documentId"),
            "name": (j.get("OmniRomExerciseId") or {}).get("name"),
            "carespaceId": (j.get("OmniRomExerciseId") or {}).get("carespaceId"),
            "order": j.get("order")}
           for j in e.get("exercises") or []]
    return {"documentId": e.get("documentId"), "title": e.get("title"), "exercises": exs,
        "_snapshot": {"documentId": e.get("documentId"), "source_updatedAt": e.get("updatedAt")}}

# type_id -> (REST plural, mapper). Other mappers added in Task 3.
TYPES = {"exercise": ("exercises", map_exercise)}

TYPES.update({
    "program-template": ("program-templates", map_program),
    "calendar-program-template": ("calendar-program-templates", map_calendar),
    "omni-rom-program": ("omni-rom-programs", map_omnirom),
    "survey-template": ("survey-templates", map_survey),
})

# type_id -> flat Strapi bracket populate params (Strapi 5 structured nested populate).
# populate=* is only one level deep, so two-level relations (a program's linked
# exercise, omnirom exercise refs, exercise modification_options.level, calendar
# day refs) need explicit per-type nested populate specs.
POPULATE = {
  "exercise": {
    # one-level name relations
    "populate[exercise_positions][fields][0]": "name",
    "populate[joints][fields][0]": "name",
    "populate[body_regions][fields][0]": "name",
    "populate[reasons][fields][0]": "name",
    "populate[equipment][fields][0]": "name",
    "populate[tags][fields][0]": "name",
    "populate[functional_goals][fields][0]": "name",
    "populate[exercise_target_muscle_groups][fields][0]": "name",
    # class-B content sub-records (need their content fields -> populate fully)
    "populate[common_mistakes]": "true",
    "populate[feedback_points]": "true",
    "populate[warm_up_suggestions]": "true",
    "populate[cool_down_recommendations]": "true",
    "populate[progression_steps]": "true",
    # modification_options + nested level (TWO levels)
    "populate[modification_options][fields][0]": "description",
    "populate[modification_options][populate][level][fields][0]": "name",
  },
  "program-template": {
    "populate[body_regions][fields][0]": "name",
    "populate[joints][fields][0]": "name",
    "populate[functional_goals][fields][0]": "name",
    "populate[reasons][fields][0]": "name",
    "populate[exercises][populate][strapiExerciseId][fields][0]": "name",
    "populate[exercises][populate][strapiExerciseId][fields][1]": "carespaceId",
  },
  "calendar-program-template": {
    "populate[reasons][fields][0]": "name",
    "populate[days][populate][exerciseProgram][fields][0]": "name",
    "populate[days][populate][exerciseProgram][fields][1]": "carespaceId",
    "populate[days][populate][omniRomProgram][fields][0]": "title",
    "populate[days][populate][omniRomProgram][fields][1]": "carespaceId",
    "populate[days][populate][surveyTemplate][fields][0]": "title",
    "populate[days][populate][surveyTemplate][fields][1]": "carespaceId",
  },
  "omni-rom-program": {
    "populate[exercises][populate][OmniRomExerciseId][fields][0]": "name",
    "populate[exercises][populate][OmniRomExerciseId][fields][1]": "carespaceId",
  },
  "survey-template": {
    "populate[surveyTemplateQuestion]": "true",
  },
}

def write_record(root, env, type_id, record):
    d = os.path.join(root, env, type_id); os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{record.get('carespaceId') or record['documentId']}.json")
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".rec-")
    with os.fdopen(fd, "w") as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return path

def snapshot(client, root, env, type_ids=None, now=None):
    type_ids = type_ids or list(TYPES)
    counts = {}
    for tid in type_ids:
        plural, mapper = TYPES[tid]
        n = 0
        for ent in client.get_all(plural, POPULATE.get(tid)):
            rec = mapper(ent)
            rec["carespaceId"] = ent.get("carespaceId")
            rec["_snapshot"]["env"] = env
            rec["_snapshot"]["fetched_at"] = now
            write_record(root, env, tid, rec); n += 1
        counts[tid] = n
    manifest = {"env": env, "fetched_at": now, "counts": counts}
    with open(os.path.join(root, env, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env", required=True)
    ap.add_argument("--types", help="comma list; default all")
    ap.add_argument("--root", default=os.environ.get("CARESPACE_MIRROR_ROOT",
                    os.path.expanduser("~/carespace-catalog-mirror")))
    a = ap.parse_args(argv)
    cfg = rest_client.resolve_config()
    client = rest_client.RestClient(cfg["host"], cfg["token"])
    tids = a.types.split(",") if a.types else None
    import datetime
    man = snapshot(client, a.root, a.env, tids, now=datetime.datetime.now().isoformat(timespec="seconds"))
    print(json.dumps(man, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
