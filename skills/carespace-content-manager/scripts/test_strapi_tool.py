import contextlib, io, json, os, tempfile, unittest
from unittest import mock
import mcp_client, strapi_tool

SECRET = "ADMIN-SECRET-VALUE"

def fake_factory(calls):
    def factory(url, auth):
        def transport(payload):
            calls.append((url, auth, payload))
            if payload.get("method") == "tools/list":
                return 200, json.dumps({"result": {"tools": [{"name": "list_exercise"},
                                                             {"name": "create_exercise"}]}})
            if payload.get("method") == "tools/call":
                body = {"results": [{"carespaceId": 7}], "pagination": {}}
                return 200, "data: " + json.dumps({"result": {"content": [
                    {"type": "text", "text": json.dumps(body)}]}})
            return 200, ""
        return transport
    return factory

class TestStrapiTool(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"STRAPI_HOST": "https://s.example/",
                                                "STRAPI_ADMIN_TOKEN": SECRET,
                                                "STRAPI_READ_TOKEN": "RO"})
        self.env.start()
        for k in ("STRAPI_MCP_URL",):
            os.environ.pop(k, None)
        self.calls = []
        self.patch = mock.patch.object(mcp_client, "_default_transport_factory",
                                       fake_factory(self.calls))
        self.patch.start()
        self.nofile = mock.patch.object(mcp_client, "_DEFAULT_ENV_FILE",
                                        os.path.join(self.dir, "none.env"))
        self.nofile.start()

    def tearDown(self):
        self.patch.stop(); self.nofile.stop(); self.env.stop()

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = strapi_tool.main(argv)
        return rc, out.getvalue()

    def test_call_uses_maestro_secrets_and_never_prints_token(self):
        rc, out = self.run_main(["call", "list_exercise", '{"pageSize": 1}'])
        self.assertEqual(rc, 0)
        self.assertNotIn(SECRET, out)
        self.assertEqual(json.loads(out)["payload"]["results"][0]["carespaceId"], 7)
        url, auth, _ = self.calls[-1]
        self.assertEqual(url, "https://s.example/mcp")
        self.assertEqual(auth, f"Bearer {SECRET}")

    def test_call_out_file_prints_summary_only(self):
        path = os.path.join(self.dir, "r.json")
        rc, out = self.run_main(["call", "list_exercise", "{}", "--out", path])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"isError": False, "out": path, "rows": 1})
        with open(path) as fh:
            self.assertIn("payload", json.load(fh))

    def test_bad_json_arguments_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc, _ = self.run_main(["call", "list_exercise", "{nope"])
        self.assertEqual(rc, 2)

    def test_check_reports_both_connections_without_tokens(self):
        rc, out = self.run_main(["check"])
        self.assertEqual(rc, 0)
        self.assertNotIn(SECRET, out); self.assertNotIn('"RO"', out)
        data = json.loads(out)
        self.assertTrue(data["mcp"]["ok"])
        self.assertTrue(data["rest"]["configured"])

    def test_tools_lists_names(self):
        rc, out = self.run_main(["tools"])
        self.assertEqual(out.split(), ["create_exercise", "list_exercise"])

    def test_missing_secrets_exit_3(self):
        os.environ.pop("STRAPI_ADMIN_TOKEN")
        with contextlib.redirect_stderr(io.StringIO()):
            rc, _ = self.run_main(["call", "list_exercise", "{}"])
        self.assertEqual(rc, 3)

if __name__ == "__main__":
    unittest.main()
