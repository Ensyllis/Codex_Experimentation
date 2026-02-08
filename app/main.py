from __future__ import annotations

import datetime
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import anthropic
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field


BASE_PATH = "/ai_personality_quiz"
MODEL = "claude-opus-4-6"

DIMENSIONS = [
    ("frustration_response", "When the world doesn't give them what they want, how do they react?"),
    ("pain_relationship", "What is their relationship with pain?"),
    ("moral_flexibility", "What does the world say is wrong that they wish could be seen as right?"),
    ("gratitude_blindspots", "What's important to them that most people take for granted?"),
    ("identity_signature", "What do they think is the most important feature people remember them by?"),
    ("life_structure", "What outlines is their life outlined by?"),
    ("moral_framework", "What constitutes a good or bad person to them?"),
    ("emotional_awareness", "What is their relationship with their own emotions?"),
    ("subconscious_drivers", "To what extent are they driven by feelings they cannot describe?"),
    ("meta_perception", "What do they think reveals the most about a person?"),
    ("value_tolerance", "What is their relationship with values they can't understand?"),
    ("expectation_rigidity", "How important is it for them that the world matches their expectations?"),
]

SYSTEM_PROMPT = """You are the interviewer for the Latent Personality Interview (LPI).
You should never directly ask the 12 core questions, but instead ask natural, friendly questions
that gradually reveal personality traits. Use reflective probing. Follow the user's energy.
If a topic is drying up, pivot gracefully.
"""


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    session_id: str
    message: str


class ExtractRequest(BaseModel):
    session_id: str


@dataclass
class SessionState:
    history: list[dict[str, str]] = field(default_factory=list)


app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount(
    f"{BASE_PATH}/static",
    StaticFiles(directory="app/static"),
    name="static",
)

SESSIONS: dict[str, SessionState] = {}


def get_session(session_id: str | None) -> tuple[str, SessionState]:
    if session_id and session_id in SESSIONS:
        return session_id, SESSIONS[session_id]
    new_id = str(uuid.uuid4())
    state = SessionState()
    SESSIONS[new_id] = state
    return new_id, state


def build_dimension_template() -> dict[str, dict[str, Any]]:
    return {
        key: {"assessment": None, "confidence": 0.0, "supporting_evidence": []}
        for key, _ in DIMENSIONS
    }


def generate_ai_reply(history: list[dict[str, str]]) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "Thanks for sharing. Could you tell me about a recent moment that felt especially "
            "meaningful or revealing to you?"
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=history,
    )
    return response.content[0].text


def extract_dimensions(history: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return build_dimension_template()

    client = anthropic.Anthropic(api_key=api_key)
    transcript = "\n".join(f"{item['role']}: {item['content']}" for item in history)
    extraction_prompt = f"""You are extracting the 12 LPI dimensions from a transcript.
Transcript:
{transcript}

Return a JSON object with the keys:
{", ".join(key for key, _ in DIMENSIONS)}
Each value must be an object with assessment (string or null), confidence (0-1), supporting_evidence (array).
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system="Return JSON only.",
        messages=[{"role": "user", "content": extraction_prompt}],
    )
    response_text = response.content[0].text
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return build_dimension_template()


@app.get(f"{BASE_PATH}/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "base_path": BASE_PATH},
    )


@app.post(f"{BASE_PATH}/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    session_id, state = get_session(payload.session_id)
    state.history.append({"role": "user", "content": payload.message})
    reply = generate_ai_reply(state.history)
    state.history.append({"role": "assistant", "content": reply})
    return ChatResponse(session_id=session_id, message=reply)


@app.post(f"{BASE_PATH}/api/extract")
async def extract(payload: ExtractRequest) -> JSONResponse:
    if payload.session_id not in SESSIONS:
        return JSONResponse({"error": "Unknown session."}, status_code=404)
    state = SESSIONS[payload.session_id]
    dimensions = extract_dimensions(state.history)
    response = {
        "interview_id": payload.session_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "dimensions": dimensions,
    }
    return JSONResponse(response)
