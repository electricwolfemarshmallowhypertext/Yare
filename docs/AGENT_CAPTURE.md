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

With `YARE_DATABASE_URL` configured, load a verified saved handoff:

```powershell
python -m cli.yare handoff load --task "fix the failing test" --verify
python -m cli.yare handoff load --run-id CAPTURE_RUN_ID --verify
python -m cli.yare verify STATE_HASH
```

Read-back checks the saved state and receipt hashes, their relationship, current-state content and any embedded source-code hash. It does not execute stored code or establish the identity of an imported evidence author. Reads issue SELECT only, with no schema changes. Failures use stable error codes and do not print a connection URL.
