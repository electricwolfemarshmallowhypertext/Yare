# Nebius Provider Routing

Status on October 7, 2026: **PASS for the live routed A/B test**. Native model
discovery, two coding runs, durable handoff, restart, and final tests were
verified. The filesystem probe used a planted canary and does not prove a
meaningful real-work boundary. B's first attempt failed during an OpenShell
startup refresh; the authorized retry completed without another refresh. The
unknown request's full reservation remains charged.

The earlier [host-controller A/B proof](NEMOTRON_HANDOFF_RESULT.md) remains valid
and separate from this result.

## Implemented Path

```text
Budgeted host controller
-> Python request inside OpenShell sandbox
-> OpenShell network/L7 policy and credential substitution
-> Nebius Token Factory
-> observed response/usage
-> existing Yare compile and CockroachDB persistence
```

OpenShell v0.1.2 uses provider attachments and native provider URLs. It no
longer provides the older `inference.local` managed route. The custom
`yare-nebius` profile grants `/usr/local/bin/python3.12` access only to:

- `GET https://api.tokenfactory.nebius.com/v1/models`
- `POST https://api.tokenfactory.nebius.com/v1/chat/completions`

The profile binds its bearer credential to the Token Factory host on port 443
under `/v1/**`. L7 rules restrict methods and paths. The credential is loaded
privately into the gateway through process environment, not command arguments.
The sandbox receives a placeholder; OpenShell substitutes the real credential
at the authorized endpoint.

References:
- [OpenShell native inference](https://docs.nvidia.com/openshell/latest/how-it-works/inference)
- [Provider profiles and credential boundaries](https://docs.nvidia.com/openshell/latest/how-it-works/providers/profiles)

## Observed Results

Both configured model IDs were verified through a real authenticated model-list
request originating inside the sandbox:

- Coding: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
- Explanation: `nvidia/nemotron-3-super-120b-a12b`

The readiness checks found a nonempty credential placeholder whose SHA256 did
not match the real API key, and no `YARE_DATABASE_URL` in either sandbox. They
reported booleans only, not credential or placeholder values.

Provider attachment enriches the effective filesystem policy with writable
`/tmp`. Therefore the routed test uses a world-readable canary under
`/opt/yare-a-notes/probe.txt`, not the original `/tmp` canary. A can read it;
B receives `PermissionError: [Errno 13]`. Both use UID/GID 1000 and Landlock
`hard_requirement`. This historical probe proves only that the two policies
treated the planted file differently, not that real work or secrets were
protected. It does not demonstrate distinct network or process scopes. The
current producer no longer creates or probes the canary. A subsequent live
handoff and final test run is recorded in
[Nemotron Resumed A/B Handoff](NEMOTRON_RESUMED_HANDOFF_RESULT.md); it does not
prove a meaningful real-work permission boundary.

A separate, credential-free request to `/v1/yare-forbidden-probe` received HTTP
403. No authorization header or credential access was used in that negative
test. A credential-bearing negative probe was not executed following an
execution safety rejection.

Routed A completed eight live coding calls, passed its four-test partial target,
and retained two full-suite normalization failures. It compiled and persisted
actual tests, diff, source, and permission result through the existing Yare path:

- Run: `nebius-routed-20261007-a`
- State hash: `46468abc026bf286aeaf154529ce8cd2824820322129111b7050d7e73ed68024`
- Receipt hash: `d1e4b5e499ee331712c92d0563a915b9a8562035cdb901851cae477d80549176`

A was stopped and deleted; sandbox listing confirmed no sandboxes before a new
B sandbox started. B authenticated model discovery and loaded A's stored
handoff. Its first generation request was admitted by the provider-derived
network and L7 rules, then OpenShell logged:

```text
DENIED api.tokenfactory.nebius.com:443
reason: L7 tunnel closed before inspection because policy changed:
policy generation is stale [captured_generation:1 current_generation:2]
```

Provider status subsequently reported `ready`, with credentials, launch
environment, and policy installed. That does not recover the interrupted
request's usage. No response or upstream request ID was captured, so its usage
could not be reconciled. Its worst-case reservation was retained, not waived.

## Refresh Investigation and Successful Retry

The refresh occurred 10.087 seconds after supervisor startup. Configuration
revisions were identical, with `policy_changed:false` and
`provider_env_changed:true`. The policy hash also stayed unchanged. This is
consistent with the startup revision mismatch reported in
[OpenShell issue 3994](https://github.com/NVIDIA/OpenShell/issues/3994).

The pinned [v0.1.2 supervisor source](https://github.com/NVIDIA/OpenShell/blob/v0.1.2/crates/openshell-supervisor/src/lib.rs#L3783)
initializes its tracked provider revision from a local credential snapshot, then
compares it with the gateway revision during polling. A first-poll mismatch can
rebuild the provider environment and advance the proxy generation. This is the
likely root cause; internal revision values were not instrumented in this test.
No OpenShell binaries, policies, credentials, or provider records were changed
to bypass the failure.

The user authorized one retry on the existing stable B sandbox while retaining
all 37 ledger entries and call 37's full reservation. An audit entry records that
decision. The `--stop-on-refresh` guard checks real supervisor logs before and
after every model call and blocks further calls if a new policy/provider refresh
appears or the refresh state cannot be verified. It does not automatically retry.

The retry used eight calls: seven Nano coding calls and one Super explanation.
B assessed A's passing partial-test command separately from the unsupported
full-suite claim, edited normalization, and passed all six tests. Independent
`unittest discover` also passed six tests; the test-file hash matched the original
fixture. B's forbidden canary read returned exit 1 with `PermissionError`, which
is preserved in its stored artifact.

- B run: `nebius-routed-20261007-b`
- State hash: `010f97bc276c45260f03d8dab9565aee1a1dd1435b17ac1eeb62a22a4605949d`
- Receipt hash: `11fe7ed64613647f2534da46ca984317060d376cac14c1f839933789eb5cf00d`
- Exact counts for the routed A/B run IDs: two rows each in `yare_runs`,
  `yare_lead_artifacts`, `yare_current_states`, and `yare_receipts`.
- Stored evidence round-tripped; A's full-test exit was 1 and B's was 0.
- Supervisor logs contained only the original startup refresh, not a repeat.

The Super explanation again confused A's assessment with B's final tests. It
is labeled unverified commentary and excluded from verified claims. This factual
review uses executed tests and stored evidence instead.

## Shared Budget

No entries were reset or removed. Before retry: 37/50 calls and conservative
ledger total USD 0.01042950. After the verified retry:

- Approved cap: 50 total calls and USD 5 total.
- Calls recorded: 45, including all original nine.
- Observed-usage estimate for 44 completed calls: USD 0.01156554.
- Call 37 retained worst-case reservation: USD 0.0020556 / 21972 tokens.
- Conservative ledger total, including reservation: USD 0.01362114.
- Remaining call allowance: 5. No more paid calls were needed for verification.
- The first 37 entries compared equal with the pre-retry snapshot; the USD 5
  and 50-call caps are unchanged.

These are token-priced estimates/reservations, not a billing statement. The
existing 200000-token safeguard remains. Resume was explicitly authorized and
audited; no automatic retry, ledger reset, or discounted unknown charge occurred.

## Setup and Exact Commands

Prerequisites: the existing authenticated `yare` gateway, Ubuntu WSL2, Docker,
and ignored `.env.nebius` containing the API key, model IDs, and database URL.
The env file is read only and was not edited.

One-time profile and provider creation:

```powershell
python -m producers.routing setup
docker build -t yare-nemotron-handoff:local examples/nemotron-handoff
docker build -t yare-nemotron-routed:local -f examples/nemotron-handoff/Dockerfile.routed examples/nemotron-handoff
```

`setup` lints and imports the profile, then creates the provider. Import is
create-only; do not blindly rerun it against an existing profile/provider.

Commands for the historical live routed attempt. Rebuilding the current images
does not recreate the canary or its permission result. The local repository path is redacted as `<repo-root>`:

```powershell
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox create --name yare-route-a --from yare-nemotron-routed:local --policy <repo-root>/examples/nemotron-handoff/agent-a-routed.yaml --provider yare-nebius-tokenfactory --detach -- python -c 'import time; time.sleep(3600)'
python -m producers.routing models --sandbox yare-route-a
python -m producers.handoff --phase a --run-id nebius-routed-20261007 --sandbox yare-route-a --routed
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox stop yare-route-a
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox delete yare-route-a
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox list
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox create --name yare-route-b --from yare-nemotron-routed:local --policy <repo-root>/examples/nemotron-handoff/agent-b-routed.yaml --provider yare-nebius-tokenfactory --detach -- python -c 'import time; time.sleep(3600)'
python -m producers.handoff --phase b --run-id nebius-routed-20261007 --sandbox yare-route-b --routed
wsl -d Ubuntu -- env XDG_CONFIG_HOME=<repo-root>/.tmp/openshell-v0.1.2/config <repo-root>/.tmp/openshell-v0.1.2/openshell -g yare sandbox provider status yare-route-b yare-nebius-tokenfactory --output json
```

The first B command failed during startup refresh. After investigating, retaining
the reservation, and receiving explicit retry authorization, the successful
command on the same stable sandbox was:

```powershell
python -m producers.handoff --phase b --run-id nebius-routed-20261007 --sandbox yare-route-b --routed --stop-on-refresh
```

For a fresh v0.1.2 sandbox, verify that the initial startup poll has completed
and provider status is ready before paid calls. The flag stops on further
refreshes; it is not an upstream fix or guarantee against future interruptions.

## Verification and Limits

Fixture/regression result: 53 tests passed (18 producer tests, 35 legacy CLI
tests). Doctor, Python syntax, legacy demo, and diff checks passed. Fixture
coverage includes routed accounting, retained reservations, endpoint restrictions,
metadata, and stopping before/after a call when refresh repeats. Secret scanning
found no API key or full database URL in changed files or raw evidence.

Raw route logs, requests/responses, readiness checks, restart and denial evidence
remain ignored under `.tmp/handoff/nebius-routed-20261007/` and
`.tmp/provider-routing/`. Private gateway credentials are not exported to the
repository. The original env file and local TODO remain ignored.

The host controller still owns sequential accounting and CockroachDB access.
OpenShell grants API access; it does not enforce a monetary budget across arbitrary
code inside a sandbox. This is a controlled producer harness, not a multi-tenant
untrusted agent service. Provider credentials persist in the local gateway;
encrypted-at-rest storage was not verified.

No legacy CLI behavior, schema, MCP access, MIT license, public frontend, or S3
behavior was changed. Free public judge access through December 15 remains
unverified. New routed test image ID:
`sha256:102c57ad440909278d0c53d3d275857399acb4fa8c3d5a5e732bd2a4cdcd050d`.
