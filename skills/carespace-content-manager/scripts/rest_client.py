#!/usr/bin/env python3
"""Stdlib Strapi REST reader for the catalog snapshot. REST (not MCP) because MCP
returns relations as {"count": N} with no ids/names; REST populate=* returns them."""
import json, os, urllib.parse, urllib.request

class ConfigError(Exception): pass

# Written by the plugin's SessionStart hook (scripts/write-env.sh) from the
# securely-stored `api_token` userConfig value (Strapi API Tokens, distinct
# from the Admin Tokens credential the MCP connection uses). Plain env vars
# take precedence; this is the fallback for Bash-tool subprocesses, which
# don't inherit the hook's CLAUDE_PLUGIN_OPTION_* variables.
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

def resolve_config(host_env="STRAPI_HOST", token_env="STRAPI_READ_TOKEN"):
    host, token = os.environ.get(host_env), os.environ.get(token_env)
    if not host or not token:
        file_values = _read_env_file(_DEFAULT_ENV_FILE)
        host = host or file_values.get(host_env)
        token = token or file_values.get(token_env)
    # Maestro secret names: STRAPI_URL (base URL) + STRAPI_API_TOKEN (the
    # read-only API Token). Used only when the names above are not set.
    host = host or os.environ.get("STRAPI_URL")
    token = token or os.environ.get("STRAPI_API_TOKEN")
    if not host or not token:
        raise ConfigError(f"set {host_env} and {token_env} (read token) in the environment, "
                          f"or the Maestro secrets STRAPI_URL and STRAPI_API_TOKEN")
    return {"host": host.rstrip("/"), "token": token}

def _default_transport(method, url, headers):
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.read().decode()

class RestClient:
    def __init__(self, host, token, transport=None):
        self.host = host.rstrip("/"); self.token = token
        self._t = transport or _default_transport

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def get_all(self, plural, extra_params=None):
        out, page = [], 1
        extra_params = extra_params or {}
        has_pop = any(str(k).startswith("populate") for k in extra_params)
        while True:
            params = {"status": "draft",
                      "pagination[page]": page, "pagination[pageSize]": 100}
            if not has_pop:
                params["populate"] = "*"
            params.update(extra_params)
            url = f"{self.host}/api/{plural}?" + urllib.parse.urlencode(params, quote_via=lambda s, safe='', encoding=None, errors=None: urllib.parse.quote(s, safe='[]', encoding=encoding, errors=errors))
            status, body = self._t("GET", url, self._headers())
            if status != 200:
                raise RuntimeError(f"GET {plural} page {page}: HTTP {status}: {body[:200]}")
            payload = json.loads(body)
            out.extend(payload.get("data") or [])
            pg = (payload.get("meta") or {}).get("pagination") or {}
            if page >= (pg.get("pageCount") or 1):
                break
            page += 1
        return out

    def get_one(self, plural, document_id):
        url = f"{self.host}/api/{plural}/{document_id}?" + urllib.parse.urlencode(
            {"populate": "*", "status": "draft"}, quote_via=lambda s, safe='', encoding=None, errors=None: urllib.parse.quote(s, safe='[]', encoding=encoding, errors=errors))
        status, body = self._t("GET", url, self._headers())
        if status == 404:
            return None
        if status != 200:
            raise RuntimeError(f"GET {plural}/{document_id}: HTTP {status}")
        return (json.loads(body).get("data")) or None
