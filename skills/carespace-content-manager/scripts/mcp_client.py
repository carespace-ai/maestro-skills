#!/usr/bin/env python3
"""Stdlib JSON-RPC client for the Strapi MCP endpoint (beta, Strapi 5.47).

Connection resolution, in order:
  1. a named `strapi-<env>` registration in ~/.claude.json (any project's
     mcpServers) — what `claude mcp add` writes, and the only source that
     supports several environments side by side;
  2. the plugin's own configured credentials, mirrored to
     ${CLAUDE_PLUGIN_DATA}/.env by the SessionStart hook (scripts/write-env.sh).

Order matters: an explicit `--env` registration always wins, so a physio with
several environments registered keeps picking between them. The plugin fallback
exists because a plugin-provided MCP server is configured through the plugin's
own .mcp.json (`${user_config.*}`) and never appears in ~/.claude.json — without
it, `run_job.py` cannot reach Strapi at all for a plugin-only install, which
breaks every multi-write flow (compose-*, scan-fill, publish-chain, restore-*).

Envelope facts verified live: list_* -> {results, pagination}; create/get/update
-> {data}; tool errors arrive as result.isError with a text payload.
"""
import json, os, time, urllib.request, urllib.error

class RegistrationError(Exception):
    pass

class VocabMiss(Exception):
    def __init__(self, name, uid):
        super().__init__(f"'{name}' is not in the live {uid} vocabulary")
        self.name, self.uid = name, uid

# Written by the plugin's SessionStart hook (scripts/write-env.sh) from the
# securely-stored `admin_token` userConfig value. Bash-tool subprocesses don't
# inherit the hook's CLAUDE_PLUGIN_OPTION_* variables, so the file is the only
# way a job runner can see them.
_DEFAULT_ENV_FILE = os.path.expanduser(
    "~/.claude/plugins/data/carespace-content-manager-carespace-skills/.env"
)

def _read_env_file(path):
    values = {}
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return values

def _mcp_url_from_base(base):
    """Maestro stores the Strapi base URL as the STRAPI_HOST secret (used
    verbatim, e.g. https://strapi.carespace.ai or
    https://preview.carespace.ai/strapi); the MCP endpoint is <base>/mcp.
    STRAPI_MCP_URL, when set, wins. Only used alongside STRAPI_ADMIN_TOKEN, so
    the read-only pair (STRAPI_HOST + STRAPI_READ_TOKEN) is never an MCP login."""
    base = (base or "").strip().rstrip("/")
    return f"{base}/mcp" if base else None

def _plugin_registration(env_file=None):
    """The plugin's own MCP credentials, or None when not configured.

    Plain env vars take precedence so a caller can override without editing the
    hook-managed file.
    """
    url = os.environ.get("STRAPI_MCP_URL") or _mcp_url_from_base(os.environ.get("STRAPI_HOST"))
    token = os.environ.get("STRAPI_ADMIN_TOKEN")
    if not url or not token:
        vals = _read_env_file(env_file or _DEFAULT_ENV_FILE)
        url = url or vals.get("STRAPI_MCP_URL")
        token = token or vals.get("STRAPI_ADMIN_TOKEN")
    if url and token:
        return {"url": url, "auth": f"Bearer {token}"}
    return None

def resolve_registration(env=None, path=None, env_file=None):
    """Resolve MCP url + auth. `env` may be None for a plugin-only install."""
    path = path or os.path.expanduser("~/.claude.json")
    named_error = None
    if env:
        try:
            with open(path) as fh:
                cfg = json.load(fh)
        except (OSError, ValueError) as e:
            # A missing/corrupt ~/.claude.json is not fatal on its own — the
            # plugin fallback below may still carry usable credentials.
            cfg, named_error = {}, str(e)
        for proj in (cfg.get("projects") or {}).values():
            srv = (proj.get("mcpServers") or {}).get(env)
            if srv:
                auth = (srv.get("headers") or {}).get("Authorization")
                if srv.get("url") and auth:
                    return {"url": srv["url"], "auth": auth}

    plugin_reg = _plugin_registration(env_file)
    if plugin_reg:
        return plugin_reg

    if not env:
        detail = "no environment name was given"
    elif named_error:
        detail = f"cannot read {path}: {named_error}"
    else:
        detail = f"no MCP registration named '{env}' found in {path}"
    hint_env = env or "strapi-<env>"
    raise RegistrationError(
        f"{detail}, STRAPI_HOST (or STRAPI_MCP_URL) + STRAPI_ADMIN_TOKEN are not set "
        f"(in Maestro: add them as secrets), and the plugin has no stored admin token. "
        f"Either configure the "
        f"plugin (/plugin configure carespace-content-manager@carespace-skills — set "
        f"the admin URL and Admin token, then /reload-plugins), or register the "
        f"environment by hand: claude mcp add --transport http {hint_env} "
        f'<strapi-base-url>/mcp --header "Authorization: Bearer <ADMIN_TOKEN>"')

def connect(ids):
    return {"connect": [{"documentId": d} for d in ids]}

def _default_transport_factory(url, auth):
    def transport(payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Authorization": auth})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    return r.status, r.read().decode()
            except urllib.error.HTTPError as e:
                if e.code in (502, 503, 504) and attempt < 2:
                    time.sleep(2 * (attempt + 1)); continue
                raise
    return transport

class McpClient:
    def __init__(self, url, auth, transport=None):
        self._transport = transport or _default_transport_factory(url, auth)
        self._ready = False
        self._id = 0

    def _rpc(self, payload):
        status, body = self._transport(payload)
        data_lines = [l[6:] for l in body.splitlines() if l.startswith("data: ")]
        if data_lines:  # SSE framing: at least one line is a `data: ` event
            body = "\n".join(data_lines)
        return json.loads(body) if body.strip() else {}

    def _handshake(self):
        if self._ready:
            return
        self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "carespace-run-job", "version": "1"}}})
        self._rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._ready = True

    def call(self, tool, arguments):
        """-> (is_error, payload). payload is parsed JSON when possible, else raw text."""
        self._handshake()
        self._id += 1
        r = self._rpc({"jsonrpc": "2.0", "id": 100 + self._id, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}})
        res = r.get("result", {})
        txt = (res.get("content") or [{}])[0].get("text", "")
        try:
            payload = json.loads(txt)
        except ValueError:
            payload = txt
        return bool(res.get("isError")), payload

    def list_tools(self):
        """Tool names the token exposes. tools/list is the heaviest call on the
        5.47 MCP beta — call it once per session at most."""
        self._handshake()
        self._id += 1
        r = self._rpc({"jsonrpc": "2.0", "id": 100 + self._id, "method": "tools/list",
                       "params": {}})
        return [t.get("name") for t in (r.get("result") or {}).get("tools") or []]

    @staticmethod
    def rows(payload):
        if isinstance(payload, dict):
            if "results" in payload:
                return payload.get("results") or []
            if isinstance(payload.get("data"), list):
                return payload["data"]
        return []

    @staticmethod
    def one(payload):
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def next_id(self, uid):
        err, payload = self.call(f"list_{uid}",
            {"status": "draft", "sort": "carespaceId:desc", "pageSize": 1, "page": 1})
        if err:
            raise RuntimeError(f"next_id({uid}): {payload}")
        rs = self.rows(payload)
        return (rs[0].get("carespaceId") or 0) + 1 if rs else 1

    def resolve_names(self, uid, names):
        idx, page = {}, 1
        while True:
            err, payload = self.call(f"list_{uid}",
                {"status": "draft", "pageSize": 100, "page": page})
            if err:
                raise RuntimeError(f"resolve_names({uid}): {payload}")
            rs = self.rows(payload)
            for x in rs:
                idx[str(x.get("name", "")).strip().lower()] = x.get("documentId")
            if len(rs) < 100:
                break
            page += 1
        out = []
        for n in names:
            did = idx.get(str(n).strip().lower())
            if not did:
                raise VocabMiss(n, uid)
            out.append(did)
        return out
