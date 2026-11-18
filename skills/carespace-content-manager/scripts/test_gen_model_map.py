import json, os, tempfile, unittest
import gen_model_map as g

def make_fixture():
    root = tempfile.mkdtemp()
    def w(path, obj):
        p = os.path.join(root, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh: json.dump(obj, fh)
    w("src/api/exercise/content-types/exercise/schema.json", {
        "kind": "collectionType",
        "info": {"singularName": "exercise", "pluralName": "exercises", "displayName": "Exercise"},
        "options": {"draftAndPublish": True},
        "attributes": {
            "name": {"type": "string", "required": True},
            "carespaceId": {"type": "integer", "required": True, "unique": True},
            "laterality": {"type": "enumeration", "enum": ["bilateral", "left", "right"]},
            "tags": {"type": "relation", "relation": "manyToMany", "target": "api::tag.tag"},
            "days": {"type": "component", "component": "calendar.day-activity", "repeatable": True},
            "scored": {"type": "boolean", "default": False},
        }})
    w("src/api/tag/content-types/tag/schema.json", {
        "kind": "collectionType",
        "info": {"singularName": "tag", "pluralName": "tags", "displayName": "Tag"},
        "options": {"draftAndPublish": True},
        "attributes": {"name": {"type": "string"},
                       "exercises": {"type": "relation", "relation": "manyToMany", "target": "api::exercise.exercise"}}})
    w("src/components/calendar/day-activity.json", {
        "attributes": {"dayNumber": {"type": "integer"},
                       "activityType": {"type": "enumeration", "enum": ["survey", "exercise"]}}})
    return root

class TestLoadModel(unittest.TestCase):
    def test_reads_types_flags_and_components(self):
        types, comps = g.load_model(make_fixture())
        self.assertEqual(set(types), {"exercise", "tag"})
        self.assertTrue(types["exercise"]["draftAndPublish"])
        self.assertEqual(types["exercise"]["plural"], "exercises")
        self.assertIn("calendar.day-activity", comps)

class TestEmitModelMap(unittest.TestCase):
    def test_relations_enums_and_hubs_rendered(self):
        types, comps = g.load_model(make_fixture())
        md = g.emit_model_map(types, comps)
        self.assertIn("manyToMany → tag", md)                # cardinality + target
        self.assertIn("enum: bilateral \\| left \\| right", md)  # enum verbatim
        self.assertIn("required; unique", md)                 # constraint rendering
        self.assertIn("`exercise` | 1 types", md)             # in-degree (tag -> exercise)
        self.assertIn("repeatable calendar.day-activity", md) # component rendering
        self.assertIn("do not hand-edit", md)

    def test_tool_name_is_singular_not_plural(self):
        types, comps = g.load_model(make_fixture())
        md = g.emit_model_map(types, comps)
        self.assertIn("`<verb>_exercise`", md)       # singular uid in the tool-name label
        self.assertNotIn("`<verb>_exercises`", md)    # plural must never leak into the label

    def test_falsy_default_is_rendered(self):
        types, comps = g.load_model(make_fixture())
        md = g.emit_model_map(types, comps)
        self.assertIn("default=False", md)  # `default: False` must not be dropped as falsy

    def test_output_is_deterministic(self):
        root = make_fixture()
        a = g.emit_model_map(*g.load_model(root))
        b = g.emit_model_map(*g.load_model(root))
        self.assertEqual(a, b)

class TestDomains(unittest.TestCase):
    def test_domain_file_includes_types_and_referenced_components(self):
        types, comps = g.load_model(make_fixture())
        md = g.emit_domain("exercise", ["exercise"], types, comps)
        self.assertIn("## exercise", md)
        self.assertIn("`carespaceId` | integer | required; unique", md)
        # the fixture exercise embeds calendar.day-activity -> its spec must be inlined
        self.assertIn("component calendar.day-activity", md)
        self.assertIn("enum: survey \\| exercise", md)

    def test_missing_domain_type_is_tolerated(self):
        types, comps = g.load_model(make_fixture())
        md = g.emit_domain("program", ["program-template", "exercise"], types, comps)
        self.assertIn("## exercise", md)          # present type rendered
        self.assertNotIn("program-template", md)  # absent type skipped, no crash

class TestGenerateAndFingerprint(unittest.TestCase):
    def test_generate_emits_all_files(self):
        files = g.generate(make_fixture())
        self.assertIn("model-map.md", files)
        for d in g.DOMAINS:
            self.assertIn(f"authoring-{d}.md", files)

    def test_fingerprint_is_content_sensitive(self):
        files = g.generate(make_fixture())
        fp1 = g.fingerprint(files)
        files["model-map.md"] += "x"
        self.assertNotEqual(fp1, g.fingerprint(files))

    def test_check_mode_exit_codes(self):
        root = make_fixture()
        out = tempfile.mkdtemp()
        self.assertIsNone(g.main(["--strapi", root, "--out", out]))       # write
        self.assertEqual(g.main(["--strapi", root, "--out", out, "--check"]), 0)   # fresh
        with open(os.path.join(out, ".fingerprint"), "w") as fh:
            fh.write("stale000000\n")
        self.assertEqual(g.main(["--strapi", root, "--out", out, "--check"]), 1)   # stale
