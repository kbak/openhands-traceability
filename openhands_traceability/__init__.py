"""Native OpenHands context plus invocation of the shared portable checker."""

import shlex
from importlib.resources import files
from pathlib import PurePosixPath


def with_traceability(context=None):
    """Attach before conversation/worktree creation, including continuation sessions."""
    from openhands.sdk import AgentContext
    from openhands.sdk.context import Skill

    directory = files("versioned_traceability") / "skills/versioned-traceability"
    loaded = Skill.load(directory / "SKILL.md")
    # ACP receives prompt text, without a skill-relative file lookup. Carry the
    # reference too, so workers need not resolve a path from the caller's install.
    content = (
        loaded.content
        + "\n\nThe referenced requirements guidance is included below; no file lookup is needed.\n"
        + '<skill-reference path="references/requirements.md">\n'
        + (directory / "references/requirements.md").read_text(encoding="utf-8")
        + "\n</skill-reference>"
    )
    skill = Skill(name=loaded.name, content=content, source=loaded.source)
    context = context or AgentContext(current_datetime=None)
    return context.model_copy(
        update={"skills": [s for s in context.skills if s.name != skill.name] + [skill]}
    )


def check(workspace, *, repo, scope, base, out, env=None, timeout=5600):
    """Run in the workspace. Exit 4 means automated checks passed, review pending.

    The caller provisions vt/OFT and supplies frozen scope outside candidate
    source. Preserve the output directory using the workspace's existing file
    transport. Completion additionally requires the caller's review lifecycle.

    repo, scope, and out must be absolute POSIX paths in the workspace's
    filesystem, including for remote workspaces. Relative paths raise ValueError.
    """
    for name, path in (("repo", repo), ("scope", scope), ("out", out)):
        if not PurePosixPath(str(path)).is_absolute():
            raise ValueError(f"{name} must be an absolute path in the workspace filesystem")
    command = [
        "python",
        "-m",
        "versioned_traceability",
        "check",
        "--repo",
        str(repo),
        "--scope",
        str(scope),
        "--base",
        base,
        "--candidate",
        "worktree",
        "--out",
        str(out),
    ]
    prefix = ["env", *[f"{key}={value}" for key, value in (env or {}).items()]]
    return workspace.execute_command(shlex.join(prefix + command), cwd=str(repo), timeout=timeout)
