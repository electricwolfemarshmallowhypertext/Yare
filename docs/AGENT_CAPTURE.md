# Agent Capture and Verified Read-Back

`yare run` prints launch instructions; it does not execute a coding agent. Claude and Codex accept positional prompts. Yare tells the agent to read its resolved context file rather than passing unsupported context flags.

Capture an explicitly authorized command with the opt-in wrapper:

```powershell
python -m cli.capture --tool codex --task "fix the failing test" --open-loop "Review the final diff" --test-command-json '["python","-m","unittest","test_example"]' -- codex "Fix the failing test"
```

This command runs the supplied process and then the supplied test command. It saves actual argv, exit status, output, repository diff, commit IDs, changed files and explicit unfinished work under ignored `.yare/captures/`. Agent output is not automatically treated as verified. A supplied command can make paid model calls; no command is launched merely by cloning or installing Yare. No hooks are installed automatically. Review captured output for secrets before publishing or archiving it. This pass has not executed a live captured agent.

Compile the emitted file through the existing path:

```powershell
python -m cli.yare lead compile --task "fix the failing test" --artifact .yare/captures/CAPTURE_RUN_ID.json
```

Discovered artifacts receive the same validation as explicit inputs. Missing,
malformed or empty inputs are rejected before saving. Different source tasks
cannot be mixed by default. To intentionally combine them, supply both
`--aggregate-tasks` and an explicit `--task "combined work"` name. The original
task labels remain in the saved artifacts. The sample lead-compile script uses
this explicit aggregation mode for its three separate sample tasks.

With `YARE_DATABASE_URL` configured, load a verified saved handoff:

```powershell
python -m cli.yare handoff load --task "fix the failing test" --verify
python -m cli.yare handoff load --run-id CAPTURE_RUN_ID --verify
python -m cli.yare verify STATE_HASH
```

Read-back checks the saved state and receipt hashes, their relationship, current-state content and any embedded source-code hash. It does not execute stored code or establish the identity of an imported evidence author. Reads issue SELECT only, with no schema changes. Failures use stable error codes and do not print a connection URL.

Tests are bound to a code-snapshot hash. A later failure supersedes an earlier
pass for the same command, and a later changed snapshot requires retesting.
Historical artifacts are retained rather than rewritten.

Git diffs do not contain untracked file contents. To preserve a new task file,
add `--include-new-file relative/path.py` before the command separator; repeat
for multiple files. Inclusion is explicit, workspace-local and limited to 128 KiB
per file. Exact bytes are stored as base64 with SHA-256; compilation and verified
loading check those bytes. No file content is executed during validation.
Untracked files not included are listed as missing contents and open work; the
capture reports that it is incomplete. Review all included bytes and command
output before sharing them. Do not include private configuration or credentials.
