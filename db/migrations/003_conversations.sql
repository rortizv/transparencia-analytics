-- Conversation history and prediction logging
-- Run after 002_hnsw_index.sql

CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT 'Nueva conversación',
    is_favorite     BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations (user_id, last_message_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_fav
    ON conversations (user_id, is_favorite, last_message_at DESC);

-- One row per turn: user message + AI response + analytics metadata
CREATE TABLE IF NOT EXISTS prediction_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id             TEXT NOT NULL,
    user_message        TEXT NOT NULL,
    assistant_response  TEXT,
    tool_invocations    JSONB NOT NULL DEFAULT '[]',
    duration_ms         INTEGER,
    is_success          BOOLEAN NOT NULL DEFAULT true,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_logs_conv
    ON prediction_logs (conversation_id, created_at ASC);

-- Auto-update conversations timestamps when a new log is appended
CREATE OR REPLACE FUNCTION update_conversation_last_message()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    UPDATE conversations
    SET last_message_at = NOW(),
        updated_at      = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prediction_logs_update_conv ON prediction_logs;
CREATE TRIGGER trg_prediction_logs_update_conv
    AFTER INSERT ON prediction_logs
    FOR EACH ROW EXECUTE FUNCTION update_conversation_last_message();

-- updated_at trigger for conversations
DROP TRIGGER IF EXISTS conversations_updated_at ON conversations;
CREATE OR REPLACE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
