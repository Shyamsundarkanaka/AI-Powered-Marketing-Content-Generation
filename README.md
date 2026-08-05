# AI-Powered Marketing Content Generation System

Production-style marketing-content generation system for Radboards (https://radboards.in/).

## Current progress

Step 7 is complete: product understanding and marketing-script generation are implemented with Gemini structured-output adapters and local tests. The next module is caption generation.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Install the Playwright browser with `playwright install`.
4. Copy `.env.example` to `.env` and fill in only the credentials needed for the module being developed.

## Architecture boundaries

- **n8n** manages the business workflow, review, scheduling, and status updates.
- **LangGraph** handles AI reasoning and agent orchestration.
- **Python modules** handle deterministic work such as scraping, database access, APIs, TTS, rendering helpers, and storage.
- **MoviePy** renders videos from the Creative Director's `video_plan.json`.

The architecture document remains the source of truth. Modules will be implemented and tested one at a time.

