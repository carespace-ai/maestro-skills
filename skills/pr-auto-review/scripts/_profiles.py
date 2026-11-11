"""Shared helpers for the per-repo review registry (repos/ + stacks/)."""
import json
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPOS, STACKS = os.path.join(ROOT, "repos"), os.path.join(ROOT, "stacks")

# Used when a repo has no profile yet: stacks guessed from the changed paths, and
# the paths that are risky in any codebase.
DEFAULT_STACKS = {
    "flutter": ["**/*.dart", "**/pubspec.yaml", "pubspec.yaml"],
    "nestjs-prisma": ["**/*.prisma", "**/*.controller.ts", "**/*.service.ts", "**/*.module.ts",
                      "**/*.dto.ts", "**/*.guard.ts", "**/migrations/**"],
    "react": ["**/*.tsx", "**/*.jsx"],
    "python": ["**/*.py", "*.py"],
    "infra": [".github/**", "**/Dockerfile*", "Dockerfile*", "**/*.bicep", "**/*.tf",
              "**/docker-compose*.yml", "docker-compose*.yml"],
}
DEFAULT_RISK = [
    {"glob": "**/migrations/**", "why": "schema / data migration"},
    {"glob": "**/*auth*", "why": "authentication / authorization"},
    {"glob": ".github/workflows/**", "why": "CI and deploy pipeline"},
    {"glob": "**/*.bicep", "why": "infrastructure"},
    {"glob": "**/Dockerfile*", "why": "runtime image"},
    {"glob": "**/.env*", "why": "environment / secrets file"},
]


def glob_re(glob):
    """Path glob → regex. `**` crosses directories, `*` and `?` do not."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(f"^{out}$")


def matches(path, globs):
    return any(glob_re(g).match(path) for g in globs)


def stack_names():
    return sorted(f[:-3] for f in os.listdir(STACKS) if f.endswith(".md"))


def repo_names():
    return sorted(d for d in os.listdir(REPOS)
                  if not d.startswith("_") and os.path.isdir(os.path.join(REPOS, d)))


def load_profile(repo):
    """The repo's profile dict, or None when it has not been onboarded."""
    path = os.path.join(REPOS, repo, "profile.json")
    if not os.path.isfile(path):
        return None
    with open(path) as fh:
        return json.load(fh)
