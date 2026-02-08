# Latent Personality Interview (LPI) MVP

This is a minimal FastAPI-based MVP for the Latent Personality Interview concept.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Then visit: `http://localhost:8080/ai_personality_quiz/`

Set `ANTHROPIC_API_KEY` to enable Claude responses. Without it, the interview uses
placeholder prompts and returns empty dimension templates.

## Claude API reference

This MVP uses the Claude Messages API style prompts and roles. See the official
Anthropic Claude documentation for details on message formatting and model usage:
https://docs.anthropic.com/en/api/messages
