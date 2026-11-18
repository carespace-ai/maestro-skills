#!/usr/bin/env python3
"""Call the Strapi MCP tools from Bash, for runs with no strapi-* MCP server
loaded (Maestro). Credentials come from the environment, which is where
Maestro puts its secrets:

  STRAPI_HOST         Strapi base URL, verbatim (MCP endpoint = <base>/mcp)
  STRAPI_ADMIN_TOKEN  Admin Token: MCP reads and writes
  STRAPI_READ_TOKEN   read-only API Token: REST (mirror, snapshots)

STRAPI_MCP_URL, when set, overrides the derived MCP endpoint.

Usage:
  strapi_tool.py check                      connection status (exit 0 = reachable)
  strapi_tool.py tools                      list tool names the Admin Token can use
  strapi_tool.py call <tool> [json|-] [--out FILE]
      call one tool; arguments as a JSON object (or '-' for stdin). Prints
      {"isError": bool, "payload": ...}; with --out the result goes to FILE
      and only a one-line summary is printed.

Token values are never printed.
"""
import argparse, json, sys
import mcp_client, rest_client

def _client(env=None):
    reg = mcp_client.resolve_registration(env)
    return mcp_client.McpClient(reg["url"], reg["auth"]), reg["url"]

def cmd_check(a):
    out = {"mcp": None, "rest": None}
    try:
        client, url = _client(a.env)
        err, payload = client.call("list_exercise", {"status": "draft", "pageSize": 1, "page": 1})
        out["mcp"] = {"url": url, "ok": not err,
                      **({"error": str(payload)[:200]} if err else {})}
    except Exception as e:  # RegistrationError, HTTP errors, bad JSON
        out["mcp"] = {"ok": False, "error": str(e)[:300]}
    try:
        cfg = rest_client.resolve_config()
        out["rest"] = {"host": cfg["host"], "configured": True}
    except rest_client.ConfigError as e:
        out["rest"] = {"configured": False, "error": str(e)}
    print(json.dumps(out, indent=2))
    return 0 if out["mcp"]["ok"] else 1

def cmd_tools(a):
    client, _ = _client(a.env)
    names = client.list_tools()
    print("\n".join(sorted(names)))
    return 0

def cmd_call(a):
    raw = sys.stdin.read() if a.args == "-" else (a.args or "{}")
    try:
        arguments = json.loads(raw)
    except ValueError as e:
        print(f"arguments are not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(arguments, dict):
        print("arguments must be a JSON object", file=sys.stderr)
        return 2
    client, _ = _client(a.env)
    err, payload = client.call(a.tool, arguments)
    result = {"isError": err, "payload": payload}
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(result, fh, indent=2)
        rows = mcp_client.McpClient.rows(payload)
        print(json.dumps({"isError": err, "out": a.out,
                          "rows": len(rows) if rows else None}))
    else:
        print(json.dumps(result, indent=2))
    return 1 if err else 0

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--env", help="named strapi-<env> registration in ~/.claude.json (optional)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("tools")
    c = sub.add_parser("call")
    c.add_argument("tool")
    c.add_argument("args", nargs="?")
    c.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        return {"check": cmd_check, "tools": cmd_tools, "call": cmd_call}[a.cmd](a)
    except mcp_client.RegistrationError as e:
        print(f"no Strapi connection: {e}", file=sys.stderr)
        return 3

if __name__ == "__main__":
    sys.exit(main())
