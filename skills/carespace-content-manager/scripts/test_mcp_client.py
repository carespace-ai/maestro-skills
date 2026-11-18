import json, os, tempfile, unittest
import mcp_client
from mcp_client import McpClient, connect, VocabMiss

class FakeTransport:
    def __init__(self, responses):            # list of (status, body_str) AFTER handshake
        self.responses = list(responses)
        self.sent = []                        # parsed JSON-RPC payloads
    def __call__(self, payload):
        self.sent.append(payload)
        m = payload.get("method")
        if m == "initialize":
            return 200, json.dumps({"jsonrpc": "2.0", "id": payload["id"],
                                    "result": {"serverInfo": {"name": "fake"}}})
        if m == "notifications/initialized":
            return 202, ""
        return self.responses.pop(0)

def rpc_result(obj, is_error=False):
    return 200, json.dumps({"jsonrpc": "2.0", "id": 1, "result":
        {"isError": is_error, "content": [{"type": "text", "text": json.dumps(obj)}]}})

class TestRegistration(unittest.TestCase):
    def test_resolves_url_and_auth_from_any_project(self):
        cfg = {"projects": {"/some/proj": {"mcpServers": {"strapi-171": {
            "type": "http", "url": "https://host/strapi/mcp",
            "headers": {"Authorization": "Bearer T"}}}}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f); path = f.name
        reg = mcp_client.resolve_registration("strapi-171", path=path)
        os.unlink(path)
        self.assertEqual(reg["url"], "https://host/strapi/mcp")
        self.assertEqual(reg["auth"], "Bearer T")

    def test_missing_registration_raises_with_hint(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"projects": {}}, f); path = f.name
        missing_env = os.path.join(tempfile.mkdtemp(), "absent.env")
        with self.assertRaises(mcp_client.RegistrationError) as ctx:
            mcp_client.resolve_registration("strapi-999", path=path, env_file=missing_env)
        os.unlink(path)
        # The hint must name BOTH recovery paths: plugin config and manual add.
        msg = str(ctx.exception)
        self.assertIn("/plugin configure", msg)
        self.assertIn("claude mcp add", msg)


class TestPluginRegistrationFallback(unittest.TestCase):
    """A plugin-provided MCP server is configured via the plugin's own .mcp.json
    (${user_config.*}) and never lands in ~/.claude.json, so the named lookup
    cannot see it. Without this fallback run_job.py can't reach Strapi at all on
    a plugin-only install."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env_file = os.path.join(self.dir, ".env")
        with open(os.path.join(self.dir, "claude.json"), "w") as fh:
            json.dump({"projects": {}}, fh)
        self.claude_json = os.path.join(self.dir, "claude.json")
        # Plain env vars take precedence over the file; keep them out of the way.
        self._saved = {k: os.environ.pop(k, None)
                       for k in ("STRAPI_MCP_URL", "STRAPI_ADMIN_TOKEN", "STRAPI_HOST")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _write_env(self, body):
        with open(self.env_file, "w") as fh:
            fh.write(body)

    def test_falls_back_to_plugin_env_file(self):
        self._write_env("STRAPI_MCP_URL=https://strapi.example.ai/mcp\n"
                        "STRAPI_ADMIN_TOKEN=ADM\n")
        reg = mcp_client.resolve_registration("strapi-live", path=self.claude_json,
                                              env_file=self.env_file)
        self.assertEqual(reg["url"], "https://strapi.example.ai/mcp")
        self.assertEqual(reg["auth"], "Bearer ADM")

    def test_named_registration_wins_over_plugin_fallback(self):
        # Several environments registered by hand must still be selectable.
        with open(self.claude_json, "w") as fh:
            json.dump({"projects": {"/p": {"mcpServers": {"strapi-171": {
                "url": "https://named/mcp",
                "headers": {"Authorization": "Bearer NAMED"}}}}}}, fh)
        self._write_env("STRAPI_MCP_URL=https://plugin/mcp\nSTRAPI_ADMIN_TOKEN=ADM\n")
        reg = mcp_client.resolve_registration("strapi-171", path=self.claude_json,
                                              env_file=self.env_file)
        self.assertEqual(reg["url"], "https://named/mcp")
        self.assertEqual(reg["auth"], "Bearer NAMED")

    def test_env_name_is_optional_when_plugin_configured(self):
        self._write_env("STRAPI_MCP_URL=https://strapi.example.ai/mcp\n"
                        "STRAPI_ADMIN_TOKEN=ADM\n")
        reg = mcp_client.resolve_registration(None, path=self.claude_json,
                                              env_file=self.env_file)
        self.assertEqual(reg["url"], "https://strapi.example.ai/mcp")

    def test_read_only_pair_alone_is_not_an_mcp_registration(self):
        # STRAPI_HOST/READ_TOKEN are the REST credential; they must never be
        # mistaken for the MCP admin credential.
        self._write_env("STRAPI_HOST=https://strapi.example.ai\n"
                        "STRAPI_READ_TOKEN=RO\n")
        with self.assertRaises(mcp_client.RegistrationError):
            mcp_client.resolve_registration("strapi-live", path=self.claude_json,
                                            env_file=self.env_file)

    def test_unreadable_claude_json_still_uses_plugin_fallback(self):
        self._write_env("STRAPI_MCP_URL=https://strapi.example.ai/mcp\n"
                        "STRAPI_ADMIN_TOKEN=ADM\n")
        reg = mcp_client.resolve_registration(
            "strapi-live", path=os.path.join(self.dir, "does-not-exist.json"),
            env_file=self.env_file)
        self.assertEqual(reg["auth"], "Bearer ADM")

    def test_plain_env_vars_take_precedence_over_file(self):
        self._write_env("STRAPI_MCP_URL=https://from-file/mcp\nSTRAPI_ADMIN_TOKEN=FILE\n")
        os.environ["STRAPI_MCP_URL"] = "https://from-env/mcp"
        os.environ["STRAPI_ADMIN_TOKEN"] = "ENVTOK"
        reg = mcp_client.resolve_registration("strapi-live", path=self.claude_json,
                                              env_file=self.env_file)
        self.assertEqual(reg["url"], "https://from-env/mcp")
        self.assertEqual(reg["auth"], "Bearer ENVTOK")

    def test_maestro_secrets_base_url_derives_mcp_endpoint(self):
        missing = os.path.join(self.dir, "no.env")
        os.environ["STRAPI_HOST"] = "https://preview.carespace.ai/strapi/"
        os.environ["STRAPI_ADMIN_TOKEN"] = "ADM"
        reg = mcp_client.resolve_registration(None, path=self.claude_json, env_file=missing)
        self.assertEqual(reg["url"], "https://preview.carespace.ai/strapi/mcp")
        self.assertEqual(reg["auth"], "Bearer ADM")

    def test_explicit_mcp_url_wins_over_base_url(self):
        missing = os.path.join(self.dir, "no.env")
        os.environ["STRAPI_HOST"] = "https://base"
        os.environ["STRAPI_MCP_URL"] = "https://explicit/mcp"
        os.environ["STRAPI_ADMIN_TOKEN"] = "ADM"
        reg = mcp_client.resolve_registration(None, path=self.claude_json, env_file=missing)
        self.assertEqual(reg["url"], "https://explicit/mcp")

    def test_base_url_without_admin_token_is_not_a_registration(self):
        missing = os.path.join(self.dir, "no.env")
        os.environ["STRAPI_HOST"] = "https://base"
        with self.assertRaises(mcp_client.RegistrationError):
            mcp_client.resolve_registration(None, path=self.claude_json, env_file=missing)

class TestClient(unittest.TestCase):
    def test_call_handshakes_once_then_calls(self):
        ft = FakeTransport([rpc_result({"data": {"documentId": "d1"}})])
        c = McpClient("u", "Bearer T", transport=ft)
        err, payload = c.call("create_exercise-tag", {"data": {"name": "X", "carespaceId": 1}})
        self.assertFalse(err)
        self.assertEqual(c.one(payload)["documentId"], "d1")
        methods = [p.get("method") for p in ft.sent]
        self.assertEqual(methods[:2], ["initialize", "notifications/initialized"])
        # second call must NOT re-handshake
        ft.responses.append(rpc_result({"data": {"documentId": "d2"}}))
        c.call("create_exercise-tag", {"data": {"name": "Y", "carespaceId": 2}})
        self.assertEqual([p.get("method") for p in ft.sent].count("initialize"), 1)

    def test_is_error_and_text_payload(self):
        ft = FakeTransport([(200, json.dumps({"jsonrpc": "2.0", "id": 1, "result":
            {"isError": True, "content": [{"type": "text", "text": "MCP error -32602: bad"}]}}))])
        c = McpClient("u", "a", transport=ft)
        err, payload = c.call("create_exercise", {"data": {}})
        self.assertTrue(err)
        self.assertIn("-32602", str(payload))

    def test_rows_normalizes_results_envelope(self):
        c = McpClient("u", "a", transport=FakeTransport([]))
        self.assertEqual(c.rows({"results": [1, 2], "pagination": {}}), [1, 2])
        self.assertEqual(c.rows({"data": [3]}), [3])
        self.assertEqual(c.rows("junk"), [])

    def test_next_id_max_plus_one_and_empty(self):
        ft = FakeTransport([rpc_result({"results": [{"carespaceId": 41}], "pagination": {}}),
                            rpc_result({"results": [], "pagination": {}})])
        c = McpClient("u", "a", transport=ft)
        self.assertEqual(c.next_id("program-template"), 42)
        self.assertEqual(c.next_id("program-template"), 1)
        args = ft.sent[2]["params"]["arguments"]     # first list call after handshake
        self.assertEqual(args["sort"], "carespaceId:desc")
        self.assertEqual(args["pageSize"], 1)

    def test_resolve_names_case_insensitive_and_miss(self):
        page = rpc_result({"results": [{"name": "Mobility", "documentId": "t1"},
                                       {"name": "Core Stability", "documentId": "t2"}],
                           "pagination": {"total": 2}})
        ft = FakeTransport([page])
        c = McpClient("u", "a", transport=ft)
        self.assertEqual(c.resolve_names("exercise-tag", ["core stability"]), ["t2"])
        ft.responses.append(page)
        with self.assertRaises(VocabMiss):
            c.resolve_names("exercise-tag", ["Yoga"])

    def test_connect_shape(self):
        self.assertEqual(connect(["a", "b"]), {"connect": [{"documentId": "a"}, {"documentId": "b"}]})

    def test_rpc_json_body_with_data_substring_not_mangled_as_sse(self):
        # A normal JSON body whose value merely CONTAINS the substring "data: "
        # (no line starts with "data: ") must parse as JSON, not be treated as SSE.
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"isError": False,
            "content": [{"type": "text", "text": json.dumps(
                {"note": "see data: here", "data": {"documentId": "d1"}})}]}})
        ft = FakeTransport([(200, body)])
        c = McpClient("u", "a", transport=ft)
        err, payload = c.call("get_exercise", {"documentId": "d1"})
        self.assertFalse(err)
        self.assertEqual(c.one(payload)["documentId"], "d1")
