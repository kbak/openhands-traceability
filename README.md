# OpenHands Traceability

Add requirement tracing and test checks to OpenHands tasks using
[Versioned Traceability](https://github.com/kbak/versioned-traceability). It uses
[OpenFastTrace](https://github.com/itsallcode/openfasttrace) to check requirement
links, compares changes against a Git baseline, runs tests, and records the
source contents checked.

Your application gives the agent instructions, runs a check after the task, and
uses the result in its existing repair and review process. This adapter provides
the instructions and forwards commands to the workspace; it does not manage the
agent's lifecycle or approve changes.

| Function | Purpose |
| --- | --- |
| `with_traceability(context=None, *, provisioned=False)` | Add instructions for maintaining requirements, code/test links, and tests to agent context. |
| `check(workspace, ...)` | Run the checker in a local or remote workspace and return its exit code and output. |
| `with_property_testing(context=None, framework=None)` | Add instructions for a focused property-testing task, with an optional library guide. |
| `with_model_checking(context=None, language=None, backend="alloy")` | Add native Alloy, Z3 SMT or CHC/Spacer modeling/execution instructions and optional Python or Daml correspondence guidance. |

For projects that need starting requirements and links, see
[document an existing project](#document-an-existing-project).

## Install

In your application's Python 3.12+ environment, install
[Versioned Traceability](https://github.com/kbak/versioned-traceability#install),
then install this adapter from its checkout:

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
A **baseline** is the starting Git commit; the **candidate** is the source being
checked. The **scope** selects what to trace and how to run tests. **Evidence** is
the saved result, logs, and source identity.

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
contents. For a scope kept in the repository, extract the reviewed version from
the fixed baseline into a task input file before implementation. Keep the supplied copy outside the candidate's control throughout the task.
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
the development procedure, requirements guidance, and definitions of check results
are still included in the prompt sent through ACP. The default includes setup
guidance for callers that have not provisioned tooling. This flag applies only to
the development instructions.

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

Once changes are committed or exported to another checkout, run `vt verify`
against that commit using the original baseline and scope. Add
`--allow-pending-review` for exit-4 evidence and complete review before
accepting the change. Instructions alone do not enforce these completion checks.

[examples/check_local.py](examples/check_local.py) runs the adapter with a local
workspace and explicit repository, scope, base, and output arguments.

## Add or maintain property tests

Development instructions include the portable
[property-testing workflow](https://github.com/kbak/versioned-traceability/blob/main/docs/property-testing.md).
It guides the agent to turn selected requirements into assertions over generated
inputs, using the project's test library and runner. No additional agent service
is required.

The instructions also cover optional [logical statements](https://github.com/kbak/versioned-traceability/blob/main/docs/property-testing.md#optional-logical-statements):
domain, assumptions, and a precise property beside its prose and existing ID.
They distinguish the requirement from test-search limits and do not treat a
written formula as proof.

For a dedicated testing task, use
`with_property_testing(context, framework="hypothesis")` instead of
`with_traceability`. The `framework` choices are `hypothesis`, `fast-check`,
`quickcheck`, and `hegel`. Omitting it includes only the general procedure;
selecting one also includes that library's guide. The project supplies its own
test dependencies.

## Model selected properties with Alloy or Z3

Use `with_model_checking(context, language="python")` for a dedicated modeling task.
It includes the portable model-checking skill, deterministic execution guide and
selected implementation guide. `language="daml"` supplies the Daml modeling and
ledger-replay guidance.
Omit `language` for the shared workflow and selected backend. For numeric checks,
use `with_model_checking(context, language="daml", backend="z3")`; it includes
the native Z3Py API and SMT execution guide. Use `backend="chc"` for unbounded modeled reachability with Spacer, including
SMT-validated invariants and reconstructed traces. The default backend is `alloy`.

The agent authors native models and mappings in the application repository.
Provision the optional Alloy JAR in the execution workspace and run `vt alloy-check`
through the project's test command when required. For Z3, install
`versioned-traceability[smt]` in the execution workspace and run `vt smt-check` or `vt chc-check`. No additional agent service is
needed. The adapter does not infer equivalence between the model and implementation
or promote bounded results into unrestricted verification claims.

## Document an existing project

Use this workflow to propose requirements and links from an existing project's
documentation, code, and tests. The function names call this *baseline recovery*:
reconstructing requirements from existing sources. The starting requirements
must be reviewed before they guide later development.

| Function | Purpose |
| --- | --- |
| `prepare_recovery(workspace, repo=..., out=None, candidate="HEAD", inputs=None, isolated=False)` | Save original source and prepare citation records. Use `isolated=True` for a separate draft. No agent or tests run. |
| `with_recovery(context=None)` | Add instructions for documenting requirements, citing sources, linking code/tests, and identifying missing checks. |
| `check_recovery(workspace, repo=..., out=None, scope=None)` | Check the proposal's edits and citations, then run OFT and existing tests. Supply `recovery=...` instead of `repo=...` to select a saved bundle. |

All filesystem arguments are absolute POSIX paths in the execution workspace;
`inputs` are repository-relative paths to inspect. Checks use the proposed
`scope.json` unless an explicit scope is supplied. Install the checker, OFT, and
project test dependencies in that workspace as for normal checks.

The default starts from a clean checkout at HEAD and leaves draft edits there.
Use `isolated=True` to work in a separate draft. That mode also permits
`candidate="worktree"` to include existing local changes. Both modes preserve the
original source and leave the proposal uncommitted.

### Run the example with an agent

The [local example](examples/recover_local.py) uses an existing Codex ACP
installation and login:

```sh
python examples/recover_local.py --repo /path/to/project \
  --focus "Session expiration behavior" \
  --input README.md --input src --input tests
```

It prepares the source records, runs an agent conversation to write the proposal,
and then calls the checker. It uses your configured model or subscription. Add
`--isolated` for a separate draft or `--out` for a new external storage directory.
The example expects tools to be installed and leaves the proposal for review.

The agent can reorganize selected Markdown documents and add or retarget code/test
references. It cites original sources, records changes to requirement IDs, and
flags inferred intent and contradictions. Implementation behavior and test
assertions are preserved. Missing property tests are recorded as recommendations;
add them after the starting requirements are reviewed and test work is authorized.

### Check and review the proposal

`check_recovery(..., preflight=True)` checks edits, citations, and links without
running tests. Exit 5 means those checks passed but tests remain unrun. A full
check also runs the existing tests; exit 4 means automation passed and review
remains required. Neither result approves the requirements.

Start with the generated `recovery-review.md`. Review the scope, proposed
requirements, original citations, ID changes, unresolved questions, and test
results. Citations establish where a statement came from; the reviewer still
assesses whether the source supports it. Once accepted, commit the reviewed
changes and run `vt check --base HEAD --candidate HEAD` on that commit.
See the [existing-project guide](https://github.com/kbak/versioned-traceability/blob/main/docs/recovery.md).

By default, both modes retain the original source and results in tool-managed
Git metadata. These files are local and do not travel with a push. Retain the
complete bundle and check outputs for shared review. The in-place mode also
creates source and claim records under `.traceability/recovery/` in the project;
include these with the reviewed documentation.

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

To check instruction delivery for documenting an existing project, add
`--recovery` to the ACP probe. These tests do not measure model behavior or review
quality.

The [CI workflow](.github/workflows/ci.yml) builds both packages, installs the
wheels, and runs the packaged adapter tests from a separate working directory.
Keep its core source revision aligned with the dependency in `pyproject.toml`.
The optional ACP/container probe runs separately.
