"""Bounded Token Factory coding smoke; all generated code runs in OpenShell."""

import argparse
import base64
import difflib
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import requests

API = "https://api.tokenfactory.nebius.com/v1"
# Observed in the official public catalog on 2026-10-07; USD per million tokens.
RATES = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (Decimal("0.06"), Decimal("0.24")),
    "nvidia/nemotron-3-super-120b-a12b": (Decimal("0.30"), Decimal("0.90")),
}
OUTPUT_CAP = 4096
TOKEN_CAP = 200000


def read_settings(path):
    settings = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        settings[name.strip()] = value.strip().strip("\"'")
    return settings


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class Budget:
    def __init__(self, path):
        self.path = path
        self.state = json.loads(path.read_text()) if path.exists() else {
            "limit_usd": "5", "max_calls": 12, "max_tokens": TOKEN_CAP, "calls": []
        }

    def reserve(self, model, payload):
        if self.state.get("blocked"):
            raise ValueError("Budget ledger blocked pending usage review")
        if model not in RATES:
            raise ValueError("No verified pricing for selected model")
        # A deliberately pessimistic byte bound plus allowance for chat framing.
        input_bound = len(json.dumps(payload).encode("utf-8")) + 8192
        if input_bound > 60000:
            raise ValueError("Request context exceeds smoke-test input bound")
        output_bound = payload["max_tokens"]
        input_rate, output_rate = RATES[model]
        cost = (input_bound * input_rate + output_bound * output_rate) / 1000000
        calls = self.state["calls"]
        spent = sum(Decimal(c["charged_usd"]) for c in calls)
        tokens = sum(c["charged_tokens"] for c in calls)
        if len(calls) >= 50 or len(calls) >= self.state["max_calls"]:
            raise ValueError("Call allowance exhausted before request")
        if spent + cost > min(Decimal("5"), Decimal(self.state["limit_usd"])):
            raise ValueError("Dollar allowance exhausted before request")
        if tokens + input_bound + output_bound > min(TOKEN_CAP, self.state["max_tokens"]):
            raise ValueError("Token allowance exhausted before request")
        calls.append({"model": model, "charged_usd": str(cost),
                      "charged_tokens": input_bound + output_bound,
                      "input_bound": input_bound, "output_bound": output_bound,
                      "status": "reserved"})
        save_json(self.path, self.state)
        return len(calls) - 1

    def settle(self, index, usage):
        call = self.state["calls"][index]
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if not isinstance(prompt, int) or not isinstance(completion, int) or min(prompt, completion) < 0:
            self.halt("Missing valid usage")
            raise ValueError("Missing valid usage; reservation retained, stopping")
        if prompt > call["input_bound"] or completion > call["output_bound"]:
            self.halt("Provider exceeded reserved token bounds")
            raise ValueError("Provider exceeded reserved token bounds; stopping")
        input_rate, output_rate = RATES[call["model"]]
        call.update(charged_usd=str((prompt * input_rate + completion * output_rate) / 1000000),
                    charged_tokens=prompt + completion, status="observed", usage=usage)
        save_json(self.path, self.state)

    def halt(self, reason):
        self.state["blocked"] = reason
        save_json(self.path, self.state)


class TokenFactory:
    def __init__(self, key, budget, evidence_dir):
        self.key, self.budget, self.evidence_dir = key, budget, evidence_dir

    def models(self, configured):
        response = requests.get(API + "/models", headers={"Authorization": "Bearer " + self.key}, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"Model list HTTP {response.status_code}")
        ids = [item["id"] for item in response.json()["data"]]
        result = []
        for value in configured:
            matches = [model for model in ids if model.casefold() == value.casefold()]
            if len(matches) != 1:
                raise ValueError("Configured model not uniquely present in live model list")
            result.append(matches[0])
        return result

    def complete(self, model, messages):
        payload = {"model": model, "messages": messages, "max_tokens": OUTPUT_CAP, "temperature": 0}
        index = self.budget.reserve(model, payload)
        started = time.monotonic()
        try:
            response = requests.post(API + "/chat/completions", json=payload,
                                     headers={"Authorization": "Bearer " + self.key}, timeout=120)
        except requests.RequestException:
            self.budget.halt("Inference transport failure; usage unknown")
            raise ValueError("Inference transport failure; reservation retained") from None
        if response.status_code != 200:
            self.budget.halt("Inference HTTP failure; usage unknown")
            raise ValueError(f"Inference HTTP {response.status_code}; reservation retained")
        result = response.json()
        # No headers, credential-bearing settings, or database URLs enter evidence.
        save_json(self.evidence_dir / f"call-{index + 1:02d}.json", {
            "provider": "Nebius Token Factory", "model": model, "request": payload,
            "response": result, "request_id": response.headers.get("x-request-id"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        })
        self.budget.settle(index, result.get("usage", {}))
        choice = result["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("Model output exhausted completion cap; stopping")
        return choice["message"]["content"]


class OpenShellRepo:
    def __init__(self, root, sandbox, test_target="test_workstate"):
        self.sandbox = sandbox
        self.test_target = test_target
        linux_root = "/mnt/" + root.drive[0].lower() + root.as_posix()[2:]
        self.cli = ["wsl", "-d", "Ubuntu", "--exec", "env",
                    "XDG_CONFIG_HOME=" + linux_root + "/.tmp/openshell-v0.1.2/config",
                    linux_root + "/.tmp/openshell-v0.1.2/openshell", "-g", "yare"]

    def execute(self, *command):
        result = subprocess.run(self.cli + ["sandbox", "exec", "--name", self.sandbox,
                                "--workdir", "/tmp/yare-task/nemotron-task", "--timeout", "30", "--no-tty",
                                "--no-login-shell", "--", *command], capture_output=True, text=True, timeout=45)
        return {"command": list(command), "exit_code": result.returncode,
                "stdout": result.stdout[:16000], "stderr": result.stderr[:16000]}

    def read(self, name):
        if name not in ("workstate.py", "test_workstate.py"):
            raise ValueError("File outside approved smoke repository")
        result = self.execute("python", "-c", "from pathlib import Path; print(Path(" + repr(name) + ").read_text())")
        if result["exit_code"] != 0:
            raise ValueError("Sandbox file inspection failed")
        return result["stdout"]

    def write(self, content):
        if not isinstance(content, str) or len(content) > 12000:
            raise ValueError("Invalid edit size")
        encoded = base64.b64encode(content.encode()).decode()
        result = self.execute("python", "-c", "import base64; from pathlib import Path; "
                              "Path('workstate.py').write_bytes(base64.b64decode('" + encoded + "'))")
        if result["exit_code"] != 0:
            raise ValueError("Sandbox edit failed")
        return result

    def test(self):
        return self.execute("python", "-m", "unittest", "-v", self.test_target)


def coding_loop(client, model, repo, evidence_dir, task_prompt=None, handoff=None, require_probe=False):
    before = repo.read("workstate.py")
    baseline = repo.test()
    messages = [{"role": "system", "content": (
        (task_prompt or "You are a coding agent fixing an isolated Python repository. Fix classify_claim: "
        "return verified only for status verified AND evidence_present True; otherwise unresolved. "
        "Keep contradictions classified as contradicted. Do not modify tests. ") +
        "Inspect both files before editing. Reply with exactly one JSON object per turn: "
        '{"action":"read","path":"workstate.py or test_workstate.py"}, '
        '{"action":"write","proposal":"explain edit","content":"full workstate.py"}, '
        '{"action":"test"}, or {"action":"done"}. '
        "Read test failures and retry a bounded edit if tests fail. Claims cannot replace test execution."
    )}, {"role": "user", "content": "Initial observed test result: " + json.dumps(baseline)}]
    if require_probe:
        messages[0]["content"] += ' Also execute {"action":"scope_probe"} before editing; record the real permission result.'
    if handoff is not None:
        messages[0]["content"] += (
            ' Before editing, return {"action":"assess_handoff", "observed_exit_code":0, '
            '"observed_test_command":<exact observed A partial-test command array>, '
            '"unverified_claim":"All full-suite tests passed", "explanation":<why this is not verified>}.'
        )
        messages.append({"role": "user", "content": "Durable Cockroach handoff, not prior chat: " + json.dumps(handoff)})
    events, inspected = [{"action": "baseline_test", "result": baseline}], set()
    wrote, passed, probed, assessed = False, False, False, False
    assessment = None
    for _ in range(16):
        answer = client.complete(model, messages)
        action = json.loads(answer.strip())
        kind = action.get("action")
        if kind == "read":
            name = action["path"]
            result = repo.read(name)
            inspected.add(name)
        elif kind == "write":
            if (require_probe and not probed) or (handoff is not None and not assessed):
                result = {"rejected": "Execute scope_probe and assess_handoff before editing."}
            elif inspected != {"workstate.py", "test_workstate.py"} or not action.get("proposal"):
                result = {"rejected": "Edit requires reading BOTH workstate.py and test_workstate.py "
                          "and an explicit proposal. No edit was applied."}
            else:
                result = repo.write(action["content"])
                wrote, passed = True, False
        elif kind == "scope_probe" and require_probe:
            result = repo.probe()
            probed = True
        elif kind == "assess_handoff" and handoff is not None:
            expected = handoff["artifact"]["evidence"]["partial_test"]["command"]
            assessed = (action.get("observed_exit_code") == 0 and
                        action.get("observed_test_command") == expected and
                        action.get("unverified_claim") == "All full-suite tests passed" and
                        bool(action.get("explanation")))
            result = {"accepted": assessed, "reason": "Compare exact stored test evidence and unverified claim."}
            if assessed:
                assessment = action
        elif kind == "test":
            result = repo.test()
            passed = wrote and result["exit_code"] == 0
        elif kind == "done":
            if not passed:
                raise ValueError("Agent ended without an observed passing change")
            break
        else:
            raise ValueError("Unsupported agent action")
        events.append({"action": action, "result": result})
        save_json(evidence_dir / "actions.json", events)
        messages.extend([{"role": "assistant", "content": answer},
                         {"role": "user", "content": json.dumps(result)}])
        if passed:
            break
    if not passed:
        raise ValueError("Coding loop ended without passing tests")
    final_test = repo.test()
    after = repo.read("workstate.py")
    if final_test["exit_code"] != 0 or before == after:
        raise ValueError("Independent final check did not confirm a passing code change")
    result = {"baseline_test": baseline, "final_test": final_test,
              "diff": "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                    fromfile="before/workstate.py", tofile="after/workstate.py")),
              "source_sha256": hashlib.sha256(after.encode()).hexdigest()}
    if handoff is not None:
        result["handoff_assessment"] = assessment
    result["scope_probes"] = [event["result"] for event in events if isinstance(event["action"], dict)
                              and event["action"]["action"] == "scope_probe"]
    save_json(evidence_dir / "coding-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    settings = read_settings(root / ".env.nebius")
    evidence = root / ".tmp" / "nebius-first-test"
    budget = Budget(evidence / "budget.json")
    client = TokenFactory(settings["NEBIUS_API_KEY"], budget, evidence)
    models = client.models([settings["NEBIUS_MODEL_ID"], settings["NEBIUS_EXPLAIN_MODEL_ID"]])
    save_json(evidence / "models.json", {"coding": models[0], "explanation": models[1],
                                        "verified_at": datetime.now(timezone.utc).isoformat()})
    result = coding_loop(client, models[0], OpenShellRepo(root, args.sandbox), evidence)
    explanation = client.complete(models[1], [
        {"role": "system", "content": "Explain only the supplied observed coding test and diff. "
         "Separate evidence from claims. This is one producer smoke, not a two-agent handoff proof. Be concise."},
        {"role": "user", "content": json.dumps(result)},
    ])
    save_json(evidence / "explanation.json", {"model": models[1], "text": explanation})
    print("coding test: PASS")
    print("explanation: received")
    print("coding model:", models[0])
    print("explanation model:", models[1])
    print("calls:", len(budget.state["calls"]))
    print("estimated USD:", sum(Decimal(c["charged_usd"]) for c in budget.state["calls"]))
    print("evidence:", evidence)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not echo request objects, settings, or credential-bearing exception text.
        print("first test: FAIL", type(error).__name__)
        raise SystemExit(1)
