import json
from pathlib import Path

import pytest
import requests
import yaml

from producers.nemotron import Budget
from producers.routing import RoutedTokenFactory

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


class FixtureRoute:
    def __init__(self, fail=False):
        self.commands = []
        self.fail = fail

    def execute(self, *command, **kwargs):
        self.commands.append(command)
        body = {"choices": [{"message": {"content": "observed answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        return {"exit_code": int(self.fail), "stdout": json.dumps({"status": 200, "body": body}),
                "stderr": ""}


def test_routed_call_uses_placeholder_and_existing_ledger(tmp_path):
    repo = FixtureRoute()
    budget = Budget(tmp_path / "budget.json")
    client = RoutedTokenFactory(repo, budget, tmp_path / "evidence")
    assert client.key is None
    assert client.complete(MODEL, [{"role": "user", "content": "task"}]) == "observed answer"
    assert "os.environ['NEBIUS_API_KEY']" in repo.commands[0][2]
    assert budget.state["calls"][0]["status"] == "observed"
    assert budget.state["calls"][0]["charged_tokens"] == 15
    evidence = json.loads((tmp_path / "evidence/call-01.json").read_text())
    assert evidence["transport"] == "OpenShell endpoint-bound provider"


def test_routed_failure_retains_reservation_and_blocks_calls(tmp_path):
    budget = Budget(tmp_path / "budget.json")
    client = RoutedTokenFactory(FixtureRoute(fail=True), budget, tmp_path)
    with pytest.raises(ValueError, match="reservation retained"):
        client.complete(MODEL, [])
    assert budget.state["calls"][0]["status"] == "reserved"
    with pytest.raises(ValueError, match="blocked"):
        client.complete(MODEL, [])


def test_routed_transport_rejects_other_api_paths(tmp_path):
    client = RoutedTokenFactory(FixtureRoute(), Budget(tmp_path / "budget.json"), tmp_path)
    with pytest.raises(ValueError, match="approved"):
        client.request("POST", "/files", {})


def test_profile_binds_only_approved_nebius_surface():
    root = Path(__file__).resolve().parents[2]
    profile = yaml.safe_load((root / "examples/nemotron-handoff/nebius-provider.yaml").read_text())
    endpoint, = profile["endpoints"]
    assert endpoint["host"] == "api.tokenfactory.nebius.com"
    assert endpoint["enforcement"] == "enforce"
    assert endpoint["rules"] == [{"allow": {"method": "GET", "path": "/v1/models"}},
                                 {"allow": {"method": "POST", "path": "/v1/chat/completions"}}]
    assert profile["binaries"] == ["/usr/local/bin/python3.12"]


def test_refresh_before_call_stops_without_spending(tmp_path, monkeypatch):
    budget = Budget(tmp_path / "budget.json")
    client = RoutedTokenFactory(FixtureRoute(), budget, tmp_path)
    client.stop_on_refresh = True
    client.refresh_baseline = {"old event"}
    monkeypatch.setattr(client, "refresh_events", lambda: {"old event", "new event"})
    with pytest.raises(ValueError, match="refresh repeated"):
        client.complete(MODEL, [])
    assert budget.state["calls"] == []
    assert budget.state["blocked"] == "OpenShell policy/provider refresh repeated"


def test_refresh_after_response_preserves_observed_usage_then_stops(tmp_path, monkeypatch):
    budget = Budget(tmp_path / "budget.json")
    client = RoutedTokenFactory(FixtureRoute(), budget, tmp_path)
    client.stop_on_refresh = True
    client.refresh_baseline = {"old event"}
    events = iter([{"old event"}, {"old event", "new event"}])
    monkeypatch.setattr(client, "refresh_events", lambda: next(events))
    with pytest.raises(ValueError, match="refresh repeated"):
        client.complete(MODEL, [])
    assert budget.state["calls"][0]["status"] == "observed"
    assert budget.state["calls"][0]["charged_tokens"] == 15
