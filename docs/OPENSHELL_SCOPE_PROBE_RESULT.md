# OpenShell Process and Network Scope Probe

Status on October 8, 2026: **PASS for isolated process identity and outbound-network policy checks.** This was a credential-free scope probe, not a new coding handoff or a rerun of the SWE-bench issues.

Both sandboxes used the same disposable `yare-scope-probe:local` image (`sha256:43007eb58303ba65121de5ae978aa01242af4841841d3e18afdd6623d207cab0`), derived from the existing public task snapshot. The derivative only made its work directory writable by the alternate non-root UID.

| Check | A | B |
| --- | --- | --- |
| Effective policy hash | `dc7a688aafb0a8839a3c4f6d22a9317a06e27f37718091da012ee2b821f8e409` | `7a50b29328374978a52d87131614d0503e2533ab47505573939ea42f66acfaa6` |
| Effective `run_as_user` / `run_as_group` | `1000` / `1000` | `1500` / `1500` |
| Runtime `id -u` | `1000`, exit 0 | `1500`, exit 0 |
| TCP to `example.com:443` from Python | `TCP_OK`, exit 0 | `PermissionError: [Errno 13] Permission denied`, exit 1 |
| OpenShell network event | `ALLOWED ... example.com:443 [policy:public_probe engine:opa]` | `DENIED ... example.com:443 [reason:transparent_tcp_policy_denied]` |

The A policy explicitly allows `/usr/local/bin/python3.12` to connect to `example.com:443`; the B policy has no outbound rule. `openshell policy get --full -o json` reported both policies as `effective`. The identical Python socket command was run in both sandboxes. The B log also recorded `reason=network connections not allowed by policy`, so the failure was not inferred solely from a Python exception.

Commands used, with the local pinned OpenShell v0.1.2 CLI and gateway; the local repository path is redacted as `<repo-root>`:

```powershell
docker build -f examples/nemotron-handoff/Dockerfile.boundary -t yare-nemotron-boundary:local examples/nemotron-handoff
docker build -f examples/nemotron-handoff/Dockerfile.scope-probe -t yare-scope-probe:local examples/nemotron-handoff
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox create --name yare-scope-final-a --from yare-scope-probe:local --policy <repo-root>/examples/nemotron-handoff/agent-a-scope-probe.yaml --detach -- python -c 'import time; time.sleep(900)'
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox create --name yare-scope-final-b --from yare-scope-probe:local --policy <repo-root>/examples/nemotron-handoff/agent-b-scope-probe.yaml --detach -- python -c 'import time; time.sleep(900)'
```

For each sandbox, the checks were `openshell policy get <name> --full -o json`, `openshell sandbox exec --name <name> --no-tty --no-login-shell -- id -u`, and the same `python -c` socket connection to `example.com:443`. Both final probe sandboxes were stopped, then the Yare gateway was stopped. `docker ps` returned no running containers.

**Limit:** These are separate scope probes. The previously completed A/B coding run still used the older same-UID policies, and this probe does not prove distinct process or network scopes for that historical run. Both sandbox logs included a startup `provider_env_changed:true` refresh observation; keep the v0.1.2 readiness and stop-on-refresh guard for any future routed model run.
