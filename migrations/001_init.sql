-- Base table already managed by persistence schema bootstrap.
-- This example adds a projects table and project_id to memories for continuity.

BEGIN;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

ALTER TABLE memories ADD COLUMN project_id TEXT DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_mem_project ON memories(project_id);

COMMIT;