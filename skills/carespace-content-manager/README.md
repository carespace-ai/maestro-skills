# Carespace content manager — skill

The Carespace catalog authoring skill, packaged as a **plain Agent Skill** rather than a Claude
Code plugin. It helps a physiotherapist author, edit, and publish catalog content — exercises,
programs, calendar templates, OmniROM programs, and surveys — in Strapi.

This repo exists because Claude Code plugins only work in Claude Code. Skills work in **Claude
chat on the web, the Chat tab in Claude Desktop, and Claude Cowork** as well, which is where the
physios are.

## How this relates to the plugin

The same skill also ships as a Claude Code plugin in
[`carespace-ai/carespace-skills`](https://github.com/carespace-ai/carespace-skills). The
authoring content is the same; the difference is entirely in setup:

| | Plugin (`carespace-skills`) | Skill (this repo) |
|---|---|---|
| Surfaces | Claude Code CLI + desktop Code tab | Everywhere skills run |
| Writes to Strapi | **Yes** | **Only in Claude Code** — chat/Cowork is draft-only ([why](#chat--cowork--️-no-write-path-today-verified)) |
| Sets up the Strapi connection | **Yes** — guided screen, token in the OS keychain | **No** — consumes a connection configured elsewhere |
| Credential storage | Keychain (`sensitive: true`) | Wherever the operator put it |

**Pick by what the person needs to do.** Committing content to the catalog means Claude Code, so
the plugin is the better fit there. This skill earns its place where the plugin can't run at
all — a physio composing exercises in chat on their phone, or Cowork drafting a program for
someone else to commit.

> **Don't install both on the same machine.** Claude would load two near-identical copies of the
> authoring instructions, one of which tells physios to install a plugin. Pick the packaging that
> matches the surface and use only that one.

## What this skill does *not* do

It **does not collect or store credentials.** It checks whether the `strapi-*` MCP tools are
present and, if they aren't, tells the physio to ask their operator — deliberately, so an access
code is never typed into a chat transcript where it would persist.

Setting up the connection is the operator's job, below.

## Install

### Claude chat / Claude Desktop chat tab / Cowork

Upload this folder as a skill via **Customize → Skills** in the sidebar. On Team and Enterprise
plans an owner can publish it once for the whole organisation instead of each physio uploading it.

Skills configured here sync through the claude.ai account, not the local `~/.claude` directory.

### Claude Code (CLI or desktop Code tab)

Clone and symlink into your personal skills directory:

```bash
git clone https://github.com/carespace-ai/carespace-content-manager.git ~/dev/carespace/carespace-content-manager
ln -s ~/dev/carespace/carespace-content-manager ~/.claude/skills/carespace-content-manager
```

If you already run the `carespace-content-manager` **plugin**, don't do this — see the warning
above.

## Connecting to Strapi (operator task)

The skill needs the `strapi-*` MCP tools present. How you provide them depends on the surface.

### Claude Code

```bash
claude mcp add strapi-live --transport http https://strapi.carespace.ai/mcp \
  --header "Authorization: Bearer <admin-token>"
```

The `strapi-<env>` naming matters: `scripts/mcp_client.py` looks for exactly that pattern in
`~/.claude.json`, so the job runners can target an environment with `--env strapi-live`. Use one
name per environment (`strapi-live`, `strapi-preview`, …).

### Chat / Cowork — ❌ no write path today (verified)

**Custom connectors cannot connect to Strapi's MCP.** This was checked against both ends, not
inferred:

- The **Add custom connector** dialog accepts a name, a URL, and — under Advanced settings — an
  OAuth Client ID and Client Secret. There is **no field for a static token or a custom header**.
- Strapi's MCP has **no OAuth support at all**. Its `401` carries no `WWW-Authenticate` header,
  which the MCP authorization spec requires of an OAuth-protected server, and all four discovery
  endpoints 404:

  ```
  401  POST /mcp                                    (no WWW-Authenticate)
  404  /.well-known/oauth-protected-resource
  404  /.well-known/oauth-protected-resource/mcp
  404  /.well-known/oauth-authorization-server
  404  /.well-known/openid-configuration
  ```

The connector speaks only OAuth; Strapi speaks only static Admin Token. There is no overlap, and
no setting on either side closes the gap.

**So on chat and Cowork this skill is draft-only.** That is still most of its value — clinical
reasoning, field completion, contraindication screening, vocabulary reconciliation and
instruction drafting all work with no connection at all. It composes the content; a physio or an
operator commits it in Claude Code.

#### If chat/Cowork needs to actually write

The fix is an **OAuth-fronting proxy**: a small service that presents itself to Claude as a
proper MCP authorization server (serving `/.well-known/oauth-protected-resource`, validating
tokens) and forwards to Strapi with the Admin Token injected server-side.

Worth noting this is not merely a workaround — it is a **better** security posture than the
plugin's, and closes gaps the current design has:

| | Admin Token on the device | OAuth proxy |
|---|---|---|
| Identity | Shared token, per environment | Per physio |
| Revocation | Rotate the token, re-onboard everyone | Revoke one grant |
| Audit | Attribution only by token/environment | Per user, centrally |
| Token at rest | Keychain, or plaintext on Windows | Never leaves the server |

Given Carespace runs on Azure, Entra ID is the obvious authorization server and Key Vault the
obvious home for the upstream Admin Token. That is a real project, not an afternoon — scope it
deliberately rather than treating it as plumbing.

## Credentials the scripts need

The script-backed flows (catalog mirror, snapshots, multi-write jobs) resolve credentials in a
documented order. Any one of these is enough:

| Purpose | Environment variables | Alternative |
|---|---|---|
| MCP writes (job runners) | `STRAPI_MCP_URL`, `STRAPI_ADMIN_TOKEN` | a named `strapi-<env>` in `~/.claude.json` |
| REST reads (mirror, snapshot) | `STRAPI_HOST`, `STRAPI_READ_TOKEN` | — |
| **Maestro** (all of the above) | secrets `STRAPI_HOST`, `STRAPI_ADMIN_TOKEN`, `STRAPI_READ_TOKEN` | MCP endpoint is `STRAPI_HOST` + `/mcp`; tool calls go through `scripts/strapi_tool.py` |

Two distinct Strapi credentials, from two different menus — don't conflate them:

- **Admin Token** (Settings → Admin Tokens) — authenticates the MCP connection this skill authors
  through.
- **API Token** (Settings → API Tokens, type **Read-only**) — a REST credential used only by the
  catalog mirror and snapshot scripts. It never touches MCP.

The base URL is used **verbatim**, with no path appended. Enter `https://strapi.carespace.ai` when
the admin opens at `…/admin` on that host, or `https://preview.carespace.ai/strapi` when Strapi
sits under a path prefix. A wrong prefix surfaces later as 404s.

`python3` is correct on macOS and Linux. On Windows resolve the interpreter first
(`python3` → `python` → `py -3`).

## Handling note

Worth being deliberate about, since this skill writes to a production clinical system:

- The **catalog is content** — exercises, programs, surveys — not patient data. Running it does
  not put ePHI into a model context.
- The **Admin Token is a production write credential**, and that's the thing to control. On chat
  and Cowork, configuration syncs through the claude.ai account and Cowork remote sessions execute
  in Anthropic-managed sandboxes. That is a different data-flow and access-control posture from
  Claude Code running locally, and it belongs in your BAA/vendor scope review rather than being
  assumed equivalent.
- Prefer a **short-lived Admin Token, one per physio per environment**. Every write is attributed
  to the token's environment (see `references/recipes.md`), so shared tokens destroy attribution.
- Nothing this skill writes reaches a patient until a physio explicitly publishes it. Publishing
  is confined to one flow (§7) and is the only place `publish_*` tools are used.

## Repo layout

```
SKILL.md              the skill itself — flows, rules, and the connection check
references/           field-level truth per content type, vocabularies, model map, recipes
reference-documents/  clinical source material (e.g. postural-report.xlsx) read via scripts/ref_docs.py — see its README to add one
templates/            job templates for the multi-write flows
scripts/              Python helpers: job runners, catalog mirror, snapshots (stdlib only)
```

Run the script tests with:

```bash
cd scripts && python3 -m unittest discover -s . -p "test_*.py"
```
