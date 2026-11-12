"""Initial schema: videos, user_tokens, watch_progress (docs/DESIGN.md section 5).

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The catalogue of sample videos; duration_seconds is the true length.
    op.execute(
        """
        CREATE TABLE videos (
            video_id         text PRIMARY KEY,
            title            text NOT NULL,
            url              text NOT NULL,
            duration_seconds integer NOT NULL CHECK (duration_seconds > 0)
        )
        """
    )
    # Credentials: only the SHA-256 hash of a token is stored, never the token.
    op.execute(
        """
        CREATE TABLE user_tokens (
            token_hash text PRIMARY KEY,
            user_id    text NOT NULL
        )
        """
    )
    # Latest state per user and video; the durable source of truth.
    op.execute(
        """
        CREATE TABLE watch_progress (
            user_id    text NOT NULL,
            video_id   text NOT NULL REFERENCES videos (video_id),
            position_s integer NOT NULL CHECK (position_s >= 0),
            duration_s integer NOT NULL CHECK (duration_s > 0),
            event_time timestamptz NOT NULL,
            session_id text NOT NULL,
            finished   boolean NOT NULL DEFAULT false,
            removed    boolean NOT NULL DEFAULT false,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, video_id)
        )
        """
    )
    # Serves the "Continue watching" query. Partial: finished and removed rows
    # are left out, so the index stays small.
    op.execute(
        """
        CREATE INDEX watch_progress_continue_idx
            ON watch_progress (user_id, event_time DESC)
            WHERE NOT finished AND NOT removed
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE watch_progress")
    op.execute("DROP TABLE user_tokens")
    op.execute("DROP TABLE videos")
