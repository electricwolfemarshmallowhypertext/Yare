"""Native Token Factory requests with OpenShell-managed credential substitution."""

import argparse
import base64
import json
import os
import subprocess
from pathlib import Path

import requests

from producers.nemotron import Budget, OpenShellRepo, TokenFactory, read_settings, save_json

PROVIDER = "yare-nebius-tokenfactory"


class RoutedTokenFactory(TokenFactory):
    transport = "OpenShell endpoint-bound provider"

    def __init__(self, repo, budget, evidence_dir, stop_on_refresh=False):
        super().__init__(None, budget, evidence_dir)
        self.repo = repo
        self.stop_on_refresh = stop_on_refresh
        self.refresh_baseline = self.refresh_events() if stop_on_refresh else set()

    def refresh_events(self):
        result = subprocess.run(self.repo.cli + ["logs", self.repo.sandbox, "-n", "300", "--source", "sandbox"],
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise ValueError("Cannot verify OpenShell refresh state")
        return {line for line in result.stdout.splitlines() if "CONFIG:DETECTED" in line and
                ("provider_env_changed:true" in line or "policy_changed:true" in line)}

    def check_refresh(self):
        if not self.stop_on_refresh:
            return
        try:
            new_events = self.refresh_events() - self.refresh_baseline
        except (ValueError, subprocess.SubprocessError):
            self.budget.halt("Cannot verify OpenShell refresh state")
            raise ValueError("Refresh verification failed; stopping") from None
        if new_events:
            save_json(self.evidence_dir / "refresh-stop.json", {"new_events": sorted(new_events)})
            self.budget.halt("OpenShell policy/provider refresh repeated")
            raise ValueError("OpenShell refresh repeated; stopping")

    def complete(self, model, messages):
        self.check_refresh()
        answer = super().complete(model, messages)
        self.check_refresh()
        return answer

    def request(self, method, path, payload=None):
        if (method, path) not in (("GET", "/models"), ("POST", "/chat/completions")):
            raise ValueError("Request outside approved Token Factory API surface")
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        code = (
            "import base64,json,os,urllib.request,urllib.error; "
            f"payload=json.loads(base64.b64decode('{encoded}')); "
            "key=os.environ['NEBIUS_API_KEY']; "
            f"request=urllib.request.Request('https://api.tokenfactory.nebius.com/v1{path}', "
            f"data=json.dumps(payload).encode() if payload is not None else None, method='{method}', "
            "headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}); "
            "response=urllib.request.urlopen(request,timeout=120); "
            "print(json.dumps({'status':response.status,'body':json.load(response),"
            "'request_id':response.headers.get('x-request-id')}))"
        )
        try:
            observed = self.repo.execute("python", "-c", code, timeout=125, output_limit=262144)
        except subprocess.SubprocessError:
            raise requests.RequestException("OpenShell transport did not return") from None
        if observed["exit_code"] != 0:
            save_json(self.evidence_dir / "routed-failure.json", {
                "method": method, "path": path, "exit_code": observed["exit_code"],
                "stderr": observed["stderr"], "stdout": observed["stdout"],
            })
            raise requests.RequestException("OpenShell routed request failed")
        try:
            result = json.loads(observed["stdout"])
            status, body = result["status"], result["body"]
        except (ValueError, KeyError):
            raise requests.RequestException("Invalid routed response") from None
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode()
        if result.get("request_id"):
            response.headers["x-request-id"] = result["request_id"]
        return response


def setup_provider(root, settings):
    cli = OpenShellRepo(root, "unused").cli
    linux_root = "/mnt/" + root.drive[0].lower() + root.as_posix()[2:]
    profile = linux_root + "/examples/nemotron-handoff/nebius-provider.yaml"
    for command in (["profile", "lint", "-f", profile], ["profile", "import", "-f", profile]):
        result = subprocess.run(cli + command, capture_output=True, text=True, timeout=45)
        if result.returncode != 0:
            raise ValueError("Provider profile setup failed")
    # Transfer the key through process environment, never command-line arguments.
    env = dict(os.environ, NEBIUS_API_KEY=settings["NEBIUS_API_KEY"])
    exported = [item for item in env.get("WSLENV", "").split(":") if item and item.split("/")[0] != "NEBIUS_API_KEY"]
    env["WSLENV"] = ":".join(exported + ["NEBIUS_API_KEY"])
    result = subprocess.run(cli + ["provider", "create", "--name", PROVIDER, "--type", "yare-nebius",
                                   "--credential", "NEBIUS_API_KEY"],
                            env=env, capture_output=True, text=True, timeout=45)
    if result.returncode != 0:
        raise ValueError("Provider credential setup failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "models"])
    parser.add_argument("--sandbox")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    settings = read_settings(root / ".env.nebius")
    if args.action == "setup":
        setup_provider(root, settings)
        print("provider: configured; credentials not displayed")
    else:
        if not args.sandbox:
            parser.error("models requires --sandbox")
        client = RoutedTokenFactory(OpenShellRepo(root, args.sandbox),
                                    Budget(root / ".tmp/nebius-first-test/budget.json"),
                                    root / ".tmp/provider-routing")
        print("routed models:", client.models([settings["NEBIUS_MODEL_ID"], settings["NEBIUS_EXPLAIN_MODEL_ID"]]))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("provider routing FAIL:", type(error).__name__)
        raise SystemExit(1)
