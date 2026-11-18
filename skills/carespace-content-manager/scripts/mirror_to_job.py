#!/usr/bin/env python3
"""Turn a mirror exercise record into a scan-fill job: filter to the writable subset,
guard against snapshot drift, and emit plan.json + records/<cid>.json for run_job."""
import argparse, json, os

DERIVED_DROP = {"is_bilateral"}   # middleware-derived from laterality; never written

def writable_record(mirror_rec):
    jr = json.loads(json.dumps(mirror_rec))
    jr["scalars"] = {k: v for k, v in (jr.get("scalars") or {}).items()
                     if k not in DERIVED_DROP and v is not None}
    return jr

def check_drift(rest_client, plural, mirror_rec):
    live = rest_client.get_one(plural, mirror_rec["documentId"])
    if not live:
        return f"record {mirror_rec['documentId']} no longer exists live"
    base = (mirror_rec.get("_snapshot") or {}).get("source_updatedAt")
    if live.get("updatedAt") != base:
        return (f"DRIFT: {mirror_rec['documentId']} changed live since snapshot "
                f"({base} -> {live.get('updatedAt')}); re-snapshot before writing")
    return None

def build_job(mirror_rec, job_dir):
    os.makedirs(os.path.join(job_dir, "records"), exist_ok=True)
    cid = mirror_rec.get("carespaceId") or mirror_rec["documentId"]
    with open(os.path.join(job_dir, "plan.json"), "w") as fh:
        json.dump({"kind": "scan-fill", "title": f"round-trip {cid}", "batch": [cid]}, fh, indent=1)
    with open(os.path.join(job_dir, "records", f"{cid}.json"), "w") as fh:
        json.dump(writable_record(mirror_rec), fh, indent=1, ensure_ascii=False)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("record", help="path to a mirror exercise record json")
    ap.add_argument("job_dir")
    ap.add_argument("--env", help="if set, drift-check against live before building")
    a = ap.parse_args(argv)
    with open(a.record) as fh:
        rec = json.load(fh)
    if a.env:
        import rest_client
        cfg = rest_client.resolve_config()
        warn = check_drift(rest_client.RestClient(cfg["host"], cfg["token"]), "exercises", rec)
        if warn:
            print(warn); return 2
    build_job(rec, a.job_dir)
    print(json.dumps({"job_dir": a.job_dir, "batch": [rec.get("carespaceId")]}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
