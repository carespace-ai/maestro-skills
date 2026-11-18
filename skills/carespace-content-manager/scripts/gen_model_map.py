#!/usr/bin/env python3
"""Generate the carespace-content-manager model references from a carespace-strapi
checkout. The generated files are the skill's schema knowledge — never hand-edit
them; re-run this instead.

    python3 gen_model_map.py --strapi PATH            # write references
    python3 gen_model_map.py --strapi PATH --check    # fresh/stale report, no writes
"""
import argparse, glob, hashlib, json, os

def load_model(strapi_root):
    types = {}
    pattern = os.path.join(strapi_root, "src", "api", "*", "content-types", "*", "schema.json")
    for p in sorted(glob.glob(pattern)):
        with open(p) as fh:
            s = json.load(fh)
        info = s.get("info", {})
        uid = info.get("singularName") or os.path.basename(os.path.dirname(p))
        types[uid] = {
            "plural": info.get("pluralName") or uid + "s",
            "display": info.get("displayName") or uid,
            "kind": s.get("kind", "collectionType"),
            "draftAndPublish": bool(s.get("options", {}).get("draftAndPublish")),
            "attributes": s.get("attributes", {}),
        }
    components = {}
    for p in sorted(glob.glob(os.path.join(strapi_root, "src", "components", "*", "*.json"))):
        with open(p) as fh:
            s = json.load(fh)
        key = os.path.basename(os.path.dirname(p)) + "." + os.path.splitext(os.path.basename(p))[0]
        components[key] = s.get("attributes", {})
    return types, components

def _target(attr):
    return (attr.get("target") or "").split(".")[-1]

def in_degree(types):
    deg = {}
    for t in types.values():
        for a in t["attributes"].values():
            if a.get("type") == "relation":
                deg[_target(a)] = deg.get(_target(a), 0) + 1
    return deg

def field_row(name, a):
    t = a.get("type", "?")
    notes = []
    if a.get("required"):
        notes.append("required")
    if a.get("unique"):
        notes.append("unique")
    if a.get("default") is not None:
        notes.append(f"default={a['default']}")
    if t == "enumeration":
        notes.append("enum: " + " \\| ".join(a.get("enum", [])))
    if t == "relation":
        notes.append(f"{a.get('relation')} → {_target(a)}")
    if t == "component":
        notes.append(("repeatable " if a.get("repeatable") else "single ") + str(a.get("component", "")))
    return f"| `{name}` | {t} | {'; '.join(notes)} |"

def type_section(uid, t, heading="##"):
    lines = [f"{heading} {uid}", "",
             f"kind: {t['kind']} · MCP tools: `<verb>_{uid}` (SINGULAR uid; possible verbs: "
             f"list/get/create/update/delete/publish/unpublish + `discard_{uid}_draft` — availability "
             f"mirrors the admin token's permissions per session) · "
             f"REST plural id: `{t['plural']}` · draftAndPublish: {t['draftAndPublish']}",
             "", "| field | type | constraints |", "|---|---|---|"]
    for name in sorted(t["attributes"]):
        lines.append(field_row(name, t["attributes"][name]))
    lines.append("")
    return lines

def _component_section(key, attrs, heading="###"):
    lines = [f"{heading} component {key}", "", "| field | type | constraints |", "|---|---|---|"]
    for name in sorted(attrs):
        lines.append(field_row(name, attrs[name]))
    lines.append("")
    return lines

def emit_model_map(types, components):
    lines = ["# Content model map (GENERATED — do not hand-edit; re-run gen_model_map.py)", "",
             f"{len(types)} content types · {len(components)} components · "
             f"{sum(1 for t in types.values() if t['draftAndPublish'])} draft-and-publish", "",
             "## Dependency hubs (in-degree: how many types point at this one)", "",
             "| type | referenced by |", "|---|---|"]
    for uid, n in sorted(in_degree(types).items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| `{uid}` | {n} types |")
    lines += ["", "Editing a hub touches every dependent — look before you write.", ""]
    for uid in sorted(types):
        lines += type_section(uid, types[uid])
    lines.append("## Components")
    lines.append("")
    for key in sorted(components):
        lines += _component_section(key, components[key])
    return "\n".join(lines).rstrip() + "\n"

# Domain membership for the per-domain authoring specs. A listed type absent from the
# checkout is skipped (renames surface via --check staleness, not a crash).
DOMAINS = {
    "exercise": ["exercise", "exercise-tag", "functional-goal",
                 "exercise-target-muscle-group", "exercise-modification-option",
                 "exercise-modification-option-level", "exercise-common-mistake",
                 "exercise-feedback-point", "exercise-warm-up-suggestion",
                 "exercise-cool-down-recommendation", "exercise-progression-step"],
    "program": ["program-template", "program-exercise-template"],
    "calendar": ["calendar-program-template"],
    "omnirom": ["omni-rom-program", "omni-rom-program-exercise", "omni-rom-exercise"],
    "survey": ["survey-template", "survey-template-question"],
}

def emit_domain(domain, uids, types, components):
    lines = [f"# Authoring spec: {domain} (GENERATED — do not hand-edit; re-run gen_model_map.py)", ""]
    comp_refs = set()
    for uid in uids:
        t = types.get(uid)
        if not t:
            continue
        lines += type_section(uid, t)
        for a in t["attributes"].values():
            if a.get("type") == "component" and a.get("component") in components:
                comp_refs.add(a["component"])
    for key in sorted(comp_refs):
        lines += _component_section(key, components[key], heading="##")
    return "\n".join(lines).rstrip() + "\n"

def generate(strapi_root):
    types, components = load_model(strapi_root)
    out = {"model-map.md": emit_model_map(types, components)}
    for domain, uids in DOMAINS.items():
        out[f"authoring-{domain}.md"] = emit_domain(domain, uids, types, components)
    return out

def fingerprint(files):
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode())
        h.update(files[name].encode())
    return h.hexdigest()[:12]

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strapi", required=True, help="path to a carespace-strapi checkout")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references"))
    ap.add_argument("--check", action="store_true", help="compare against recorded fingerprint; no writes")
    a = ap.parse_args(argv)
    files = generate(a.strapi)
    fp = fingerprint(files)
    fp_path = os.path.join(a.out, ".fingerprint")
    if a.check:
        recorded = None
        if os.path.exists(fp_path):
            with open(fp_path) as fh:
                recorded = fh.read().strip()
        fresh = recorded == fp
        print(json.dumps({"current": fp, "recorded": recorded, "fresh": fresh,
                          "note": "stale => the committed references no longer match the schemas; re-run without --check"}))
        return 0 if fresh else 1
    os.makedirs(a.out, exist_ok=True)
    for name, content in files.items():
        with open(os.path.join(a.out, name), "w") as fh:
            fh.write(content)
    with open(fp_path, "w") as fh:
        fh.write(fp + "\n")
    print(json.dumps({"wrote": sorted(files), "fingerprint": fp}))

if __name__ == "__main__":
    raise SystemExit(main())
