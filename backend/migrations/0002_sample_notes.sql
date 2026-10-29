-- Sample notes table. Same shape as Fast's Alembic revision 002.
CREATE TABLE IF NOT EXISTS note (
    id uuid PRIMARY KEY,
    title varchar(255) NOT NULL,
    content varchar(10000) NOT NULL,
    owner_id uuid NOT NULL REFERENCES "user" (id),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_note_owner_id ON note (owner_id);
