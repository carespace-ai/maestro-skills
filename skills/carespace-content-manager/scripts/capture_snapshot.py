#!/usr/bin/env python3
"""Capture the catalog's authored exercise content to a portable snapshot JSON —
the input that restore_snapshot.py / the repo's 035 migration replay into another
environment.

Read-only (REST, like the catalog mirror): needs STRAPI_HOST / STRAPI_READ_TOKEN.
Captures the labels + dosing + prose scalars and the body-region / functional-goal
/ tag / equipment relations BY NAME (documentIds differ per environment; carespaceId
is the match key). By default it captures the reviewed drafts
(review_status=unreviewed, movement_complexity set) — the authoring work — not the
raw, unlabelled records.

    python3 scripts/capture_snapshot.py --out authored-content.json
    python3 scripts/capture_snapshot.py --out snap.json --all   # every labelled record

Output shape matches the repo's scripts/migrations/data/authored-content.json so a
snapshot captured here can be dropped straight into that migration, and vice-versa.
"""
import argparse
import datetime
import json
import sys

import rest_client

SCALARS = [
    "laterality", "movement_complexity", "joint_demand", "balance_demand",
    "weight_bearing", "floor_transfer_required", "requires_assistance",
    "progression_level", "contraindication_status", "equipment_status",
    "default_sets", "default_reps", "default_hold_seconds",
    "default_daily_frequency", "default_weekly_frequency",
    "contraindications", "instructions", "alignment_tips", "breathing", "precautions",
]

# Populate each relation as just its name (matches snapshot.py's mirror populate).
POPULATE = {
    "populate[body_regions][fields][0]": "name",
    "populate[functional_goals][fields][0]": "name",
    "populate[tags][fields][0]": "name",
    "populate[equipment][fields][0]": "name",
    "status": "draft",
    "filters[movement_complexity][$notNull]": "true",
}


def _names(rel):
    if isinstance(rel, list):
        return [x.get("name") for x in rel if isinstance(x, dict) and x.get("name")]
    return []


def capture(client, only_unreviewed=True):
    params = dict(POPULATE)
    if only_unreviewed:
        params["filters[review_status][$eq]"] = "unreviewed"
    out = []
    for ex in client.get_all("exercises", params):
        if ex.get("carespaceId") is None:
            continue
        rec = {"carespaceId": ex.get("carespaceId"), "name": ex.get("name")}
        for f in SCALARS:
            rec[f] = ex.get(f)
        rec["body_regions"] = _names(ex.get("body_regions"))
        rec["functional_goals"] = _names(ex.get("functional_goals"))
        rec["tags"] = _names(ex.get("tags"))
        rec["equipment"] = _names(ex.get("equipment"))
        out.append(rec)
    out.sort(key=lambda r: r["carespaceId"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="path to write the snapshot json")
    ap.add_argument("--env", default="", help="label recorded in the snapshot meta")
    ap.add_argument("--all", action="store_true",
                    help="capture every labelled record, not just unreviewed drafts")
    a = ap.parse_args(argv)

    cfg = rest_client.resolve_config()
    client = rest_client.RestClient(cfg["host"], cfg["token"])
    rows = capture(client, only_unreviewed=not a.all)

    equipment_vocab = sorted({e for r in rows for e in r["equipment"]})
    snap = {
        "_meta": {
            "source_env": a.env or cfg.get("host", ""),
            "captured": datetime.datetime.now().isoformat(timespec="seconds"),
            "count": len(rows),
            "note": ("Authored exercise content. Matched by carespaceId; relations by "
                     "name. Replay with restore_snapshot.py / migration 035 (drafts only)."),
            "equipment_vocab_referenced": equipment_vocab,
        },
        "exercises": rows,
    }
    with open(a.out, "w") as fh:
        json.dump(snap, fh, indent=1, ensure_ascii=False)
    print(json.dumps({"out": a.out, "captured": len(rows),
                      "equipment_vocab_referenced": equipment_vocab}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
