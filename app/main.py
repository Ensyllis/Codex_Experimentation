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

# ---------------------------------------------------------------------------
# Personality dimensions -- focused on values, relationships, and lifestyle
# ---------------------------------------------------------------------------
DIMENSIONS = [
    (
        "relationship_with_family",
        "What is this person's relationship with their family like? "
        "Write a short narrative read about the dynamics, closeness, tension, "
        "and role family plays in their identity.",
    ),
    (
        "relationship_with_self",
        "How does this person relate to themselves? "
        "Describe their inner dialogue, self-worth, self-criticism, and how "
        "comfortable they are being alone with their own thoughts.",
    ),
    (
        "sources_of_escape_and_fun",
        "Where does this person go -- physically, mentally, or emotionally -- "
        "when they need to escape or have fun? What activities or places recharge them?",
    ),
    (
        "what_makes_them_happy",
        "What genuinely makes this person happy? Not what they think should make "
        "them happy, but what actually lights them up based on the conversation.",
    ),
    (
        "what_makes_them_sad",
        "What makes this person sad or heavy? What losses, disappointments, or "
        "unmet needs weigh on them?",
    ),
    (
        "what_they_value_in_people",
        "What qualities does this person look for and value most in other people? "
        "What earns their trust and respect?",
    ),
    (
        "values_above_average",
        "What values does this person hold MORE strongly than the general population? "
        "Things they prioritize that most people would not rank as high.",
    ),
    (
        "values_below_average",
        "What values does the general population hold that this person does NOT "
        "prioritize as much? Things most people care about that this person is "
        "relatively indifferent to.",
    ),
    (
        "emotional_awareness",
        "How aware is this person of their own emotions? Do they process feelings "
        "openly or suppress them? Describe their emotional intelligence and blind spots.",
    ),
    (
        "identity_and_self_image",
        "How does this person see themselves, and how do they want to be seen? "
        "What is the gap between their self-image and reality?",
    ),
    (
        "moral_framework",
        "What constitutes right and wrong for this person? Where are they rigid "
        "and where are they flexible? What moral hills would they die on?",
    ),
    (
        "response_to_adversity",
        "How does this person handle setbacks, frustration, and pain? "
        "Do they fight, withdraw, adapt, or something else?",
    ),
    (
        "need_for_control",
        "How important is it for this person that the world matches their "
        "expectations? How do they handle uncertainty and disorder?",
    ),
    (
        "hidden_drivers",
        "What drives this person beneath the surface -- motivations they may not "
        "be fully conscious of? Unspoken needs, fears, or desires inferred from "
        "the conversation.",
    ),
]

# ---------------------------------------------------------------------------
# System prompt -- Chris Voss inspired What/How investigative interviewing
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a deeply perceptive interviewer conducting a personality interview.

YOUR INTERVIEWING STYLE:
- Use calibrated "What" and "How" questions to get the person to explain themselves \
at deeper levels, inspired by Chris Voss's investigative questioning technique.
- When someone gives you a surface-level answer, dig underneath it. Ask them WHAT \
about that thing matters to them, or HOW it makes them feel, or WHAT that says about \
who they are.
- Use tactical empathy: label their emotions and mirror their language to show you \
understand, then follow up with a deeper question.
- Never ask yes/no questions. Never ask "why" directly -- "why" makes people \
defensive. Reframe "why" as "what made you..." or "how did you come to...".

QUESTION FLOW EXAMPLES:
- If they say "I like being alone" --> "What is it about being alone that feels \
better than being around people?"
- If they say "I don't like drama" --> "It sounds like you've had to deal with a lot \
of that. How does it affect you when people around you create chaos?"
- If they say "I value loyalty" --> "What does loyalty actually look like to you in \
practice? How do you know when someone has crossed that line?"
- If they share something emotional --> Label it first ("It sounds like that really \
stuck with you"), then ask "What about that experience changed how you see things?"

RULES:
- Keep responses SHORT -- 1 to 3 sentences max. You are a listener, not a lecturer.
- Ask only ONE question at a time.
- Follow the person's energy. If they go deep on something, stay there. If a topic \
is drying up, pivot gracefully.
- Early in the conversation, keep it light -- ask about their day, what they've been \
into lately, what they do for fun. Let depth emerge naturally.
- Never tell them you are analyzing them. Never mention personality dimensions or \
psychology jargon. Just be a curious, warm human who is genuinely interested.
- Never directly ask the personality dimension questions. Let the answers emerge \
through natural conversation.
- Occasionally use mirroring (repeat the last 1-3 key words they said as a question) \
to get them to elaborate.
- If they give a short or deflecting answer, gently probe: "What do you mean by \
that?" or "How so?"
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
            "Thanks for sharing. Could you tell me about a recent piece of media "
            "that really touched your soul?"
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=history,
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Extraction -- produces narrative personality reads, not just labels
# ---------------------------------------------------------------------------
def extract_dimensions(history: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return build_dimension_template()

    client = anthropic.Anthropic(api_key=api_key)
    transcript = "\n".join(f"{item['role']}: {item['content']}" for item in history)

    dim_descriptions = "\n".join(
        f'- "{key}": {description}' for key, description in DIMENSIONS
    )

    extraction_prompt = f"""\
Below is a transcript of a personality interview. Your job is to write a \
personality read for each dimension listed below.

IMPORTANT INSTRUCTIONS:
- For each dimension, write the "assessment" as a SHORT NARRATIVE PARAGRAPH \
(2-4 sentences) describing your read on this person. Write it like you are \
explaining this person to someone who wants to understand them deeply. Use \
second person ("they") perspective.
- Do NOT just restate what they said. Interpret it. Read between the lines. \
Explain what it reveals about who they are.
- For "supporting_evidence", pull 1-3 direct or near-direct quotes from the \
transcript that support your read.
- For "confidence", rate 0.0-1.0 how confident you are based on how much \
evidence the conversation provided for that dimension. If the conversation \
barely touched on it, give low confidence and still provide your best guess.

DIMENSIONS:
{dim_descriptions}

TRANSCRIPT:
{transcript}

Return a JSON object with the following structure. Keys are the dimension names \
listed above. Each value is an object with:
- "assessment": string (your narrative read)
- "confidence": number (0.0 to 1.0)
- "supporting_evidence": array of strings (quotes from the transcript)

Return ONLY the JSON object, no other text."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system="You are a personality analyst. Return valid JSON only.",
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
