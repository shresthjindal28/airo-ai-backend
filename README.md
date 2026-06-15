# airo-ai

AI job worker service for Aevomed. Processes transcription and transcript finalization jobs.

## Setup

```bash
cd airo-ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env` with the same `DATABASE_URL` as airo-api plus R2, Redis, and `SARVAM_API_KEY`.

## Run

```bash
# Worker
python -m app.workers.runner

# Health API
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Realtime transcription test

1. Run migration in airo-api: `alembic upgrade head`
2. Start Redis: `redis-server`
3. Start airo-api with `REDIS_URL` configured
4. Start airo-ai worker with `SARVAM_API_KEY` configured
5. Doctor starts session, uploads audio chunks via presigned URLs, registers chunks
6. Worker transcribes each chunk → `transcript_segments` + Redis event
7. Frontend connects WebSocket: `ws://host/api/v1/ws/sessions/{session_id}/transcript?token=JWT`
8. End session → `transcript_finalize` job merges segments into `transcripts`
