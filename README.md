# OpenHands Traceability

Add requirement tracing and test checks to OpenHands tasks using
[Versioned Traceability](https://github.com/kbak/versioned-traceability). It uses
[OpenFastTrace](https://github.com/itsallcode/openfasttrace) to check requirement
links, compares changes against a Git baseline, runs tests, and records the
source contents checked.

For normal development this package provides two functions:

| Function | Purpose |
| --- | --- |
| `with_traceability(context=None, *, provisioned=False)` | Add instructions for maintaining requirements, references, and tests to an agent's context. |
| `check(workspace, ...)` | Run the checker in a local or remote workspace and return its exit code and output. |

Your application attaches the instructions before the task starts, runs the
check after implementation, and returns failures to the agent for repair. It
uses the check result and its existing review process to decide when the task is
complete.

Development and recovery contexts include the portable
[semantic contract](https://github.com/kbak/versioned-traceability/blob/main/versioned_traceability/skills/versioned-traceability/references/semantics.md)
alongside their procedural guidance. Agents receive the definitions and evidence
limits directly, including through ACP, without resolving Markdown links.

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

Use `with_traceability(context, provisioned=True)` when the caller has already
provisioned the checker runtime. This omits standalone installation instructions;
the complete development procedure, requirements guidance and semantic contract
still cross the ACP boundary inline. The default includes setup guidance for
callers that have not provisioned tooling. Recovery context is unchanged.

Include relevant requirement IDs and any existing task context in that message.
When saved check evidence is available, the caller or agent can use
`vt explain ID [ID ...] --compact --evidence /path/to/evidence.json` in the
workspace to assemble missing context with one graph load. The portable skill
guides selective source reads and review of related unchanged behavior. The caller
still selects relevant IDs; the adapter does not infer the task's impact scope.

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
file transport. The portable check prints status, counts, review state, exact
artifact paths and bounded failure excerpts. Send that feedback to a repair
session, opening full logs/reports when needed; no adapter-specific report parser
is required. An earlier passing bundle cannot replace a failed invocation.

The shared skill asks agents to review the full candidate diff and related
behavior, then review repair deltas and affected links without routinely repeating
completed reads. The configured test command runs within each check. A caller's
independent completion check and existing review gates still apply.

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

## Recover a baseline before development

The recovery adapter uses the portable tool's retained original snapshots and
OFT reverse-specification guidance. Clean checkouts use in-place recovery by
default; isolated drafting is optional. It adds three functions:

| Function | Purpose |
| --- | --- |
| `prepare_recovery(workspace, repo=..., out=None, candidate="HEAD", inputs=None, isolated=False)` | Preserve original source and prepare recovery in the checkout; optionally create an isolated draft. No model or tests run. |
| `with_recovery(context=None)` | Include the full recovery procedure and citation contract in agent context. |
| `check_recovery(workspace, repo=..., out=None, scope=None)` | Find the active in-place recovery, validate the proposal and citations, then run OFT and tests. Supply `recovery=...` instead of `repo=...` for an explicit bundle. |

All filesystem arguments are absolute POSIX paths on the execution workspace.
`inputs` are repository-relative paths. With no explicit scope, validation uses
the proposed scope.json in the recorded workspace. Provision the portable
tool, OFT, and project test dependencies on that workspace as for normal checks.
Omitting output paths selects tool-managed storage; explicit paths must be new.
Original snapshots and logs stay outside tracked project files. In-place source
and claims records under `.traceability/recovery/` travel with the proposed
baseline. In-place preparation requires a clean checkout and preserves the branch
and HEAD; an isolated draft can capture existing work with candidate="worktree".

The runnable [local recovery example](examples/recover_local.py) uses your
existing Codex ACP installation and login:

```sh
python examples/recover_local.py --repo /path/to/project \
  --focus "Session expiration behavior" \
  --input README.md --input src --input tests
```

It prepares the bundle, runs a recovery conversation, then has the caller invoke
the deterministic check. By default the agent edits the checkout for normal Git
review, with the original snapshot and results retained in the portable tool's
Git metadata storage. Use --out for an explicit external location. Add --isolated
to keep the original checkout unchanged; its default storage is temporary. This example
does run an agent and may consume your normal model/subscription allowance.
It leaves edits uncommitted and review pending. It does not install tools, change
CI, publish, or accept the proposed baseline.

The shared recovery instructions allow selected Markdown documents to be reorganized,
rewritten, consolidated or moved while preserving the original snapshot. Agents record
cited explanations and mappings for changed or removed requirement IDs; the portable
checker retains documentation-review.json. Code logic and test assertions remain
protected; coverage comments can be retargeted as requirements move or split.

The result is always a proposal. Exit 4 leaves review pending even if OFT and
tests pass; source citations establish provenance, not truth or approval. Review
the scope, inferred promises, changes in meaning, ID mappings, links, contradictions
and test evidence. Preserve
the recovery bundle and acceptance decision when adopting it, then run normal
`vt check` on the actual committed baseline. See the portable
[recovery guide](https://github.com/kbak/versioned-traceability/blob/main/docs/recovery.md).

Callers own scope selection, baseline acceptance, and the transition into normal
development. The adapter supplies shared instructions and forwards preparation
and validation commands; callers apply their existing review and completion policy.

To probe native recovery-context delivery without a live model, run
`python tests/check_acp_context.py --recovery` in a disposable container as
described in the test instructions above.

### Recovery feedback

The shared recovery skill uses a bounded extraction pass and a short omissions
pass, recording deferred work in Markdown rather than requiring an exhaustive
catalog. `check_recovery(..., preflight=True)` forwards `--preflight` to check
proposal edits, citations and tracing without running tests. Exit 5 means the
preflight was otherwise clean but validation is incomplete; it is never a passing
development check. Full checks retain their existing exit codes.

Read the generated `recovery-review.md` first. It distinguishes proposal checks
from trace/test results and links the detailed evidence. The local example uses
durable Git storage by default in both recovery modes. Retain the complete source
bundle and check outputs for transfer; Git metadata is not pushed with a branch.
