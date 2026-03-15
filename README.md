# Peblo Quiz Engine

An AI-powered backend system that ingests educational PDFs, extracts structured content, generates adaptive quiz questions using **Google Gemini**, and serves them through clean REST APIs — with RAG-powered semantic search, quality validation, and caching built in.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                        │
│                                                                  │
│  POST /ingest          → PDF Extractor → Gemini Embeddings       │
│  POST /generate-quiz   → Gemini LLM → Validator → Dedup Check   │
│  GET  /quiz            → TTL Cache → Supabase Query              │
│  POST /submit-answer   → Smart Answer Checker → Adaptive Engine  │
│  GET  /search          → Gemini Embeddings → pgvector RAG        │
│  GET  /student/profile → Adaptive Difficulty Profile             │
└─────────────────────────┬────────────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │  Supabase PostgreSQL  │
              │  + pgvector extension │
              │                       │
              │  sources              │
              │  chunks  (embedding)  │
              │  questions (embedding │
              │            + quality) │
              │  student_answers      │
              │  student_profiles     │
              └───────────────────────┘
```

### Data Flow

```
PDF Upload
  └─► pdfplumber extracts text
        └─► clean + chunk (~300 words each)
              └─► infer grade/subject/topic
                    └─► Gemini text-embedding-004 (768-dim vector)
                          └─► store in Supabase (sources + chunks)

POST /generate-quiz
  └─► fetch chunks from DB
        └─► Gemini 2.5 Flash generates 3 questions/chunk (MCQ + T/F + Fill)
              └─► Gemini validates quality (score 0–1)
                    └─► embedding generated for each question
                          └─► cosine similarity check vs existing questions
                                └─► accept if valid + not duplicate
                                      └─► store with quality_score + embedding

GET /quiz
  └─► check TTL cache (5 min)
        └─► query Supabase with filters (topic/difficulty/subject/grade/type)
              └─► cache result + return

POST /submit-answer
  └─► smart answer check:
        1. exact match (case-insensitive)
        2. alias table (O2=Oxygen, H2O=Water, CO2=Carbon dioxide …)
        3. Gemini semantic equivalence (FillBlank only)
  └─► update adaptive difficulty profile
        correct_streak >= 3 → level up (easy → medium → hard)
        wrong answer       → level down
```

---

## Tech Stack

| Layer       | Choice                                | Reason                        |
|-------------|---------------------------------------|-------------------------------|
| Framework   | FastAPI                               | Fast, async, auto Swagger UI  |
| Database    | Supabase (PostgreSQL + pgvector)      | Free hosted DB + vector search|
| LLM         | Google Gemini 2.5 Flash (free)        | Generation + embeddings + eval|
| PDF parsing | pdfplumber                            | Reliable text extraction      |
| Caching     | In-memory TTL cache                   | Zero-dependency, fast         |

---

## Project Structure

```
peblo-quiz-engine/
├── app/
│   ├── main.py                  # FastAPI app + CORS + static files
│   ├── database.py              # Supabase client
│   ├── models.py                # Table name constants
│   ├── routers/
│   │   ├── ingest.py            # POST /ingest
│   │   ├── quiz.py              # POST /generate-quiz, GET /quiz, cache endpoints
│   │   ├── answers.py           # POST /submit-answer, GET /student/{id}/profile
│   │   └── search.py            # GET /search (RAG semantic search)
│   └── services/
│       ├── pdf_extractor.py     # PDF parsing, chunking, topic inference
│       ├── quiz_generator.py    # Gemini generation + validation + dedup pipeline
│       ├── question_validator.py# Gemini quality evaluator + semantic dedup
│       ├── answer_checker.py    # Smart answer matching (alias + Gemini semantic)
│       ├── embeddings.py        # Gemini text-embedding-004 (with cache)
│       ├── adaptive.py          # Adaptive difficulty logic
│       └── cache.py             # TTL in-memory cache
├── migrations/
│   └── schema.sql               # Full DB schema (run once in Supabase SQL Editor)
├── static/
│   └── index.html               # Modern Gen-Z UI dashboard
├── sample_outputs/
│   ├── extracted_chunks.json
│   ├── generated_questions.json
│   └── api_responses.json
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- [Supabase](https://supabase.com) account (free)
- [Google AI Studio](https://aistudio.google.com/app/apikey) Gemini API key (free)

### 2. Clone and install

```bash
git clone <your-repo-url>
cd peblo-quiz-engine

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
```

### 4. Set up database

Run the following in **Supabase → SQL Editor**:

```sql
-- Core tables
CREATE TABLE IF NOT EXISTS sources (...);   -- see migrations/schema.sql
-- + chunks, questions, student_answers, student_profiles

-- pgvector for RAG
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE chunks    ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS embedding vector(768);
ALTER TABLE questions ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 0.7;

CREATE OR REPLACE FUNCTION match_chunks(query_embedding vector(768), match_count int DEFAULT 5)
RETURNS TABLE (chunk_id text, source_id text, subject text, topic text, grade int, text text, similarity float)
LANGUAGE sql STABLE AS $$
  SELECT chunk_id, source_id, subject, topic, grade, text,
    1 - (embedding <=> query_embedding) AS similarity
  FROM chunks WHERE embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding LIMIT match_count;
$$;
```

Full schema: see `migrations/schema.sql`

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8080
```

- UI:       http://localhost:8080
- API docs: http://localhost:8080/docs

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ingest` | Upload PDF → extract, chunk, embed, store |
| `POST` | `/generate-quiz` | Generate questions via Gemini (with validation + dedup) |
| `GET`  | `/quiz` | Get questions (filters: topic, difficulty, subject, grade, type, min_quality) |
| `POST` | `/submit-answer` | Submit answer → smart check → adaptive feedback |
| `GET`  | `/search?query=` | Semantic RAG search over ingested content |
| `GET`  | `/student/{id}/profile` | Adaptive difficulty profile |
| `GET`  | `/cache/stats` | Cache hit statistics |
| `DELETE` | `/cache` | Clear all caches |

---

## Key Features

### Smart Answer Matching
FillBlank answers checked in 3 steps:
1. Exact match (case-insensitive)
2. Alias table — O2 = Oxygen, H2O = Water, CO2 = Carbon dioxide, etc.
3. Gemini semantic equivalence check

### Adaptive Difficulty
```
3 correct in a row  →  easy → medium → hard  (level up, streak resets)
Wrong answer        →  hard → medium → easy  (level down, streak resets)
```

### Question Pipeline (Optional Features — All Implemented)
```
Generated question
  ├─ Quality validation by Gemini (score 0–1, reject if < 0.60)
  ├─ Exact duplicate check (text match)
  ├─ Semantic duplicate check (cosine similarity > 0.92 = reject)
  └─ Store with quality_score + embedding
```

### RAG Semantic Search
```
GET /search?query=photosynthesis in plants
  → Gemini embeds the query (768-dim)
  → pgvector cosine similarity search over chunk embeddings
  → Returns top-N most semantically relevant chunks
```

---

## Database Schema

| Table | Key Columns |
|-------|-------------|
| `sources` | source_id, filename, grade, subject |
| `chunks` | chunk_id, source_id, topic, text, **embedding** |
| `questions` | question_id, chunk_id, type, answer, difficulty, **quality_score**, **embedding** |
| `student_answers` | student_id, question_id, selected_answer, is_correct |
| `student_profiles` | student_id, current_difficulty, correct_streak, total_answered |

---

## Adaptive Difficulty Logic

```python
if correct:
    streak += 1
    if streak >= 3:
        difficulty = next_level  # easy → medium → hard
        streak = 0
else:
    streak = 0
    difficulty = previous_level  # hard → medium → easy
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key (free) |
| `GEMINI_MODEL` | Model name (default: gemini-2.5-flash) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service role key (full DB access) |
| `SUPABASE_ANON_KEY` | Anon key (public read) |

---

## Sample Outputs

See `sample_outputs/` for:
- `extracted_chunks.json` — chunk structure after PDF ingestion
- `generated_questions.json` — questions generated by Gemini
- `api_responses.json` — example responses for all endpoints
