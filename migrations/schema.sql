-- Peblo Quiz Engine — Database Schema
-- Run this in the Supabase SQL Editor if you prefer manual setup.
-- (The app also auto-creates these tables on startup via SQLAlchemy.)

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    source_id   VARCHAR(50)  UNIQUE NOT NULL,
    filename    VARCHAR(255) NOT NULL,
    grade       INTEGER,
    subject     VARCHAR(100),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    chunk_id    VARCHAR(100) UNIQUE NOT NULL,
    source_id   VARCHAR(50)  NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    grade       INTEGER,
    subject     VARCHAR(100),
    topic       VARCHAR(100),
    text        TEXT         NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS questions (
    id          TEXT PRIMARY KEY,
    question_id VARCHAR(100) UNIQUE NOT NULL,
    chunk_id    VARCHAR(100) NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    question    TEXT         NOT NULL,
    type        VARCHAR(20)  NOT NULL,   -- MCQ | TrueFalse | FillBlank
    options     JSONB,                   -- array for MCQ/TrueFalse, null for FillBlank
    answer      TEXT         NOT NULL,
    difficulty  VARCHAR(10)  NOT NULL,   -- easy | medium | hard
    subject     VARCHAR(100),
    topic       VARCHAR(100),
    grade       INTEGER,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_answers (
    id              TEXT PRIMARY KEY,
    student_id      VARCHAR(100) NOT NULL,
    question_id     VARCHAR(100) NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    selected_answer TEXT         NOT NULL,
    is_correct      BOOLEAN      NOT NULL,
    submitted_at    TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id                  TEXT PRIMARY KEY,
    student_id          VARCHAR(100) UNIQUE NOT NULL,
    current_difficulty  VARCHAR(10)  DEFAULT 'easy',
    correct_streak      INTEGER      DEFAULT 0,
    total_answered      INTEGER      DEFAULT 0,
    total_correct       INTEGER      DEFAULT 0,
    updated_at          TIMESTAMPTZ  DEFAULT NOW()
);
