import os
import json
import logging
from typing import List, Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_api_exceptions

load_dotenv()
logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Volunteer Coordinator AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Gemini Setup ─────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_FALLBACKS = (
    "gemini-2.5-flash",
    "gemini-3.8-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
)


def get_model_candidates() -> List[str]:
    preferred = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [preferred] if preferred else []
    for m in MODEL_FALLBACKS:
        if m not in candidates:
            candidates.append(m)
    return candidates


def load_volunteers() -> List[Dict[str, Any]]:
    with open("volunteers.json", "r", encoding="utf-8") as f:
        return json.load(f)["volunteers"]


class TaskRequest(BaseModel):
    task_description: str


# ── Rule-Based Fallback Matching ─────────────────────────────────────────────
def rule_based_match(task_text: str, volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    task = task_text.lower()
    scored = []
    for v in volunteers:
        score = 0
        reasons = []
        for skill in v.get("skills", []):
            if skill.lower() in task:
                score += 3
                reasons.append(f"skills in '{skill}'")
        if v.get("location", "").lower() in task:
            score += 2
            reasons.append(f"located in {v['location']}")
        if v.get("availability", "").lower() in task:
            score += 2
            reasons.append(f"available {v['availability']}")
        score += v.get("experience_years", 0) * 0.5
        score += v.get("past_tasks", 0) * 0.1

        if not reasons:
            reasons.append(f"{v.get('experience_years', 0)} years experience across {v.get('past_tasks', 0)} past assignments")

        reason_str = f"Strong match based on {', '.join(reasons)}."
        scored.append({"volunteer": v, "score": score, "reason": reason_str})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    matches = []
    for i, item in enumerate(top):
        vol = dict(item["volunteer"])
        vol["rank"] = i + 1
        vol["reason"] = item["reason"]
        matches.append(vol)
    return matches


# ── AI Matching with Gemini ──────────────────────────────────────────────────
def gemini_match(task_text: str, volunteers: List[Dict[str, Any]]) -> List[Dict[str, Any]] | None:
    if not GEMINI_API_KEY:
        return None

    volunteers_summary = [
        {
            "name": v["name"],
            "skills": v.get("skills", []),
            "availability": v.get("availability", ""),
            "location": v.get("location", ""),
            "experience_years": v.get("experience_years", 0),
            "past_tasks": v.get("past_tasks", 0),
        }
        for v in volunteers
    ]

    prompt = f"""You are an intelligent volunteer coordinator.
Evaluate the following list of volunteers against the requested task:
TASK: "{task_text}"

VOLUNTEERS:
{json.dumps(volunteers_summary, indent=2)}

Select the TOP 3 most suitable volunteers based on skills, location convenience, availability, and experience.
Return ONLY valid JSON matching this exact structure with no extra text or markdown formatting:
[
  {{
    "name": "Volunteer Name",
    "reason": "1-2 concise sentences explaining why they are an ideal fit for this specific task."
  }}
]
"""

    for model_id in get_model_candidates():
        try:
            model = genai.GenerativeModel(model_id)
            res = model.generate_content(prompt)
            raw = res.text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            if isinstance(data, list) and len(data) > 0:
                name_map = {v["name"]: v for v in volunteers}
                matches = []
                for idx, item in enumerate(data[:3]):
                    name = item.get("name")
                    if name in name_map:
                        vol = dict(name_map[name])
                        vol["rank"] = idx + 1
                        vol["reason"] = item.get("reason", "Top AI-recommended match.")
                        matches.append(vol)
                if matches:
                    return matches
        except (google_api_exceptions.GoogleAPIError, json.JSONDecodeError, Exception) as e:
            logger.warning("Gemini model %s matching failed: %s", model_id, e)
            continue

    return None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "running", "project": "Volunteer Coordinator AI"}


@app.get("/volunteers")
def get_volunteers():
    return {"volunteers": load_volunteers()}


@app.post("/match")
def match_volunteers(request: TaskRequest):
    volunteers = load_volunteers()
    task = request.task_description.strip()

    matches = gemini_match(task, volunteers)
    if not matches:
        matches = rule_based_match(task, volunteers)

    return {"matches": matches}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)