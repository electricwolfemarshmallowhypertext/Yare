import pytest

from cli import archive, storage, yare


def compiled():
    return {"task": "task", "deterministic_hash": "state", "current_state": {},
            "proof": {"run_id": "run-a"}, "validation": {"ok": True}}


def isolate_compile(monkeypatch):
    monkeypatch.setattr(yare, "_lead_collect_artifact_paths", lambda root, explicit: [])
    monkeypatch.setattr(yare, "_lead_compile_packet", lambda root, artifacts, task: compiled())


def test_database_failure_preserves_previous_exports(tmp_path, monkeypatch):
    isolate_compile(monkeypatch)
    output = tmp_path / ".sticky/current-state.json"
    output.parent.mkdir()
    output.write_text("previous")
    def fail(**kwargs):
        raise storage.StorageError("offline")
    monkeypatch.setattr(storage, "persist_lead_compile", fail)
    with pytest.raises(storage.StorageError, match="local=unchanged"):
        yare.compile_lead_state(tmp_path, "task", [])
    assert output.read_text() == "previous"
    assert not list((output.parent / "receipts").glob("*.jsonl"))


def test_archive_failure_keeps_committed_memory_exports(tmp_path, monkeypatch, capsys):
    isolate_compile(monkeypatch)
    monkeypatch.setattr(storage, "persist_lead_compile", lambda **kwargs: True)
    def fail(**kwargs):
        raise archive.ArchiveError("offline")
    monkeypatch.setattr(archive, "archive_lead_compile", fail)
    _, state, _, receipt, _, uris = yare.compile_lead_state(tmp_path, "task", [])
    assert state.exists() and receipt.exists()
    assert uris == []
    assert "cockroach=committed; local=written; s3=incomplete" in capsys.readouterr().err


class Cursor:
    def __init__(self, rows=()):
        self.rows, self.queries = rows, []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def execute(self, query, args=()):
        self.queries.append((query, args))
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=()):
        self.cur = Cursor(rows)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def cursor(self):
        return self.cur
    def commit(self):
        pass


def test_compile_appends_events_without_schema_or_updates():
    conn = Connection()
    storage.persist_lead_compile(compiled(), [], {"receipt_hash": "receipt"},
                                 database_url="unused", connect_func=lambda url: conn)
    queries = "\n".join(query for query, _ in conn.cur.queries)
    assert "INSERT INTO yare_events" in queries
    assert "INSERT INTO yare_run_snapshots" in queries
    assert "SET CLUSTER" not in queries and "CREATE TABLE" not in queries
    assert "DO UPDATE" not in queries


def test_timeline_keeps_repeated_state_events():
    conn = Connection([("same", "later", "task", "run-a", "receipt2", {}),
                       ("same", "earlier", "task", "run-a", "receipt1", {})])
    rows = storage.memory_timeline(database_url="unused", connect_func=lambda url: conn)
    assert [row["receipt_hash"] for row in rows] == ["receipt1", "receipt2"]
    assert "FROM yare_events" in conn.cur.queries[0][0]


def test_search_scope_is_applied_before_candidate_limit():
    conn = Connection()
    storage.search_memory("human review", 3, database_url="unused", task="task",
                          connect_func=lambda url: conn)
    assert len(conn.cur.queries) == 2
    for query, args in conn.cur.queries:
        assert "COALESCE(cs.packet_json->>'task', r.task) = %s" in query
        assert "task" in args


@pytest.mark.parametrize("query,section,text", [
    ("who must sign off before we ship?", "human approval items", "Release approval required"),
    ("which files were modified?", "what changed", "workstate.py"),
    ("anything blocked waiting on a person", "human approval items", "Release approval required"),
])
def test_plain_questions_rank_matching_sections_above_vector_collision(query, section, text):
    conn = Connection([("what is true", 0.01, "unrelated", "Deployment completed"),
                       (section, 1.1, "relevant", text)])
    rows = storage.search_memory(query, 3, database_url="unused", task="task",
                                 connect_func=lambda url: conn)
    assert rows[0]["section_name"] == section
    assert rows[0]["source_text"] == text
    assert len(rows) == 1
