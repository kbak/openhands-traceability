# OpenHands Traceability

Add requirement tracing and test checks to OpenHands tasks using
[Versioned Traceability](https://github.com/kbak/versioned-traceability). It uses
[OpenFastTrace](https://github.com/itsallcode/openfasttrace) to check requirement
links, compares changes against a Git baseline, runs tests, and records the
source contents checked.

This package provides two functions:

| Function | Purpose |
| --- | --- |
| `with_traceability(context=None)` | Add instructions for maintaining requirements, references, and tests to an agent's context. |
| `check(workspace, ...)` | Run the checker in a local or remote workspace and return its exit code and output. |

Your application attaches the instructions before the task starts, runs the
check after implementation, and returns failures to the agent for repair. It
uses the check result and its existing review process to decide when the task is
complete.

## Install

In your application's Python 3.12+ environment, install
[Versioned Traceability](https://github.com/kbak/versioned-traceability#install),
then install this package from its checkout:

```sh
python -m pip install .
```

Compatible OpenHands SDK versions are declared in [pyproject.toml](pyproject.toml)
and installed as a dependency.

The workspace that runs checks needs Versioned Traceability, Git, Java 17+, and
the project's test dependencies. Install OFT there:

```sh
python -m versioned_traceability install-oft
```

A local workspace can use the application environment. Provision a remote
workspace separately; installing a package on the client does not install it on
the remote machine.

## Prepare the task

Set up requirements, references, and a scope file using the
[Versioned Traceability guide](https://github.com/kbak/versioned-traceability#check-a-change).
The adapter requires these inputs for every check:

| Input | Meaning |
| --- | --- |
| `repo` | The project's Git repository root. |
| `scope` | A trusted JSON file selecting paths, coverage rules, and the test command. |
| `base` | The starting commit or ref to compare against. Use a fixed commit hash across implementation and repairs. |
| `out` | A new evidence directory outside the checked repository. |

`repo`, `scope`, and `out` must be absolute POSIX paths in the workspace's
filesystem. For a remote workspace, these are paths on the remote machine.
Relative paths raise `ValueError` before a command is sent to the workspace.

The scope may be maintained in the project repository or in separate
configuration. This adapter requires an explicit file and reads its current
contents. For a repository-owned scope, have the caller extract the approved
version from the pinned baseline into a task input file before implementation.
Keep the supplied copy outside the candidate's control throughout the task.
The portable CLI can read a baseline's root `scope.json` directly when `--scope`
is omitted.

Choose a new output path for each run. The adapter always checks the current
worktree, including uncommitted changes.

## Attach task instructions

Call `with_traceability` before creating a conversation or server worktree.
It supplies the shared procedure and requirements guidance as prompt text, so
remote agents can read them without accessing files from the caller's installation.
The caller must also send the actual task, repository, scope, baseline, and
evidence location to the agent.

This local example assumes a configured `codex-acp` installation. Replace the
paths and `BASE_COMMIT` with your task's inputs. An existing remote workspace can
be passed in place of `LocalWorkspace`.

```python
from openhands.sdk import Conversation
from openhands.sdk.agent import ACPAgent
from openhands.sdk.workspace import LocalWorkspace
from openhands_traceability import with_traceability

repo = "/workspaces/project"
scope = "/workspaces/task-inputs/scope.json"
base_commit = "BASE_COMMIT"
workspace = LocalWorkspace(working_dir=repo)
agent = ACPAgent(
    acp_command=["codex-acp"],
    agent_context=with_traceability(),
)
conversation = Conversation(agent=agent, workspace=workspace)
try:
    conversation.send_message(f"""
Implement session expiration according to req~session-expiration~1 and add tests.

Repository: {repo}
Scope: {scope}
Baseline: {base_commit}
Evidence output: /workspaces/task-output/agent-check-1
""")
    conversation.run()
finally:
    conversation.close()
```

Pass an existing `AgentContext` to `with_traceability` to preserve its
instructions. Resumed conversations use their saved agent configuration; attach
the skill again when creating a fresh repair session.

## Run a check

After the agent finishes, have your application run a check with the same task
inputs and a fresh output directory:

```python
from openhands_traceability import check

result = check(
    workspace,
    repo=repo,
    scope=scope,
    base=base_commit,
    out="/workspaces/task-output/check-1",
)
```

`check` calls `workspace.execute_command` and returns its command result. Use
`env` to pass environment variables and `timeout` to set the command timeout in
seconds (default 5600).

Preserve `result.exit_code` and the full output directory using the workspace's
file transport. Read stdout/stderr and the retained trace/test logs when a check
fails. An earlier passing bundle cannot replace a failed invocation.

| Exit | Handling |
| --- | --- |
| 0 | Automated checks passed; apply the task's code review requirements. |
| 4 | Automated checks passed; specification/test changes need review. |
| 1, 2, 3 | Check failed or could not establish successful validation. |

After export, run `vt verify` against the actual commit. Add
`--allow-pending-review` for exit-4 evidence and complete review before
accepting the change. Instructions alone do not enforce these completion checks.

[examples/check_local.py](examples/check_local.py) runs the adapter with a local
workspace and explicit repository, scope, base, and output arguments.

## Tests

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests check native skill parsing, serialized context, path validation, and
command forwarding. The optional [ACP probe](tests/check_acp_context.py) checks
instruction delivery on initial and repair turns against a local scripted
endpoint. Run it in a fresh disposable container with Codex/ACP installed; it
requires no model credentials:

```sh
python tests/check_acp_context.py
```

These tests do not measure model behavior or review quality.
