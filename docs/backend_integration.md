# Backend & Scheduled Ingestion Integration Guide

This guide demonstrates how to integrate the **Self-Healing Job Scraper** into external backends (FastAPI, Flask), task queues (Celery, RQ), and serverless/cron environments using the new callable API.

---

## 1. FastAPI Integration (Lifespan & Endpoints)

FastAPI can manage the bot's background scheduler within its application lifespan. The scheduler runs concurrently with your API server without blocking incoming HTTP requests.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import asyncio

from bot import start_bot, run_once, JobNotifierBot
from domain.job_posting import JobPosting

# Optional: Real-time broadcast callback (e.g. WebSocket, Discord, Database)
async def handle_new_jobs(postings: list[JobPosting]):
    print(f"🎉 New jobs found: {len(postings)}")
    for job in postings:
        print(f"  - [{job.company}] {job.title} -> {job.url}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Start bot in non-blocking mode on server startup
    bot: JobNotifierBot = await start_bot(
        block=False,
        run_initial_scrape=False,  # Don't delay server start
        on_jobs_scraped=handle_new_jobs,
    )
    app.state.bot = bot
    yield
    # 2. Clean shutdown on server exit
    await bot.stop()


app = FastAPI(title="Job Notifier API", lifespan=lifespan)


@app.get("/api/bot/status")
async def get_bot_status():
    """Health check & status endpoint."""
    bot: JobNotifierBot = app.state.bot
    status = await bot.get_status()
    return status.model_dump()


@app.post("/api/bot/scrape/{site_name}")
async def trigger_manual_scrape(site_name: str):
    """Trigger an on-demand scrape for a specific site."""
    bot: JobNotifierBot = app.state.bot
    result = await bot.run_site(site_name)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Scrape failed")
    return {
        "site": result.site_name,
        "valid_postings_count": len(result.postings),
        "postings": [p.model_dump() for p in result.postings[:10]],
    }
```

---

## 2. Serverless / Cron Task (Celery, AWS Lambda, Cloud Run)

For stateless or single-run execution, use `run_once()`:

```python
import asyncio
from bot import run_once

async def execute_cron_job():
    # Scrapes all active sites once and returns results
    results = await run_once()
    for res in results:
        print(f"Site {res.site_name}: {len(res.postings)} jobs scraped in {res.execution_time_seconds:.2f}s")

if __name__ == "__main__":
    asyncio.run(execute_cron_job())
```

---

## 3. Switching AI Providers (Gemini, OpenAI, Ollama, Groq, Mock)

The system is fully decoupled from any single AI vendor. You can switch models via environment variables or programmatically in code.

### Option A: Via Environment Variables (`.env`)

#### Google Gemini:
```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=AIzaSy...
```

#### OpenAI:
```env
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
AI_API_KEY=sk-...
```

#### Local Ollama (No API Key Required):
```env
AI_PROVIDER=ollama
AI_MODEL=llama3
AI_BASE_URL=http://localhost:11434/v1
```

#### Groq (Ultra-Fast Healing):
```env
AI_PROVIDER=groq
AI_MODEL=llama-3.3-70b-versatile
AI_API_KEY=gsk_...
AI_BASE_URL=https://api.groq.com/openai/v1
```

### Option B: Programmatic Injection (Custom Client)

```python
from bot import start_bot
from healing.ai_provider import LLMProviderFactory

# Create a Groq client programmatically
groq_client = LLMProviderFactory.create_client(
    provider="groq",
    api_key="your-groq-key",
    model_name="llama-3.3-70b-versatile",
)

bot = await start_bot(
    llm_client=groq_client,
    block=False,
)
```
