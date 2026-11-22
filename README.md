# Volunteer AI Coordinator

Matches volunteers to NGO tasks. Describe a task in plain text and get the top 3 volunteers, ranked, with a reason for each.

**Live app:** https://volunteer-ai-coordinator.onrender.com (free hosting: the first load can take up to ~50 seconds)

## Build note
Team project (Team HQ DOPAMINE: Monomoy Dikshit, Samir Kumar Shaw, Samiksha Singh) for Solution Challenge 2026 – Build with AI. My part: [fill in]. Built with AI-assisted development.

## Screenshots
![Matching page](screenshots/match.png)

## How it works
1. The user describes a task on the web page.
2. The FastAPI backend (`main.py`) sends the task and the volunteer list to Google Gemini, asking for the top 3 as JSON.
3. If Gemini is unavailable or rate-limited, a rule-based fallback scores volunteers instead (+3 per matching skill, +2 location, +2 availability, plus a small bonus for experience).
4. The page shows the 3 matches. The API response includes a `source` field (`gemini` or `rule-based`) so you can see which one answered.

## Tech stack
- Backend: Python, FastAPI, Uvicorn
- AI: Google Gemini API
- Data: `volunteers.json` (sample volunteer list)
- Frontend: HTML, CSS, JavaScript (`index.html`, `dashboard.html`), served by the backend
- Hosting: Render

## Run locally
```bash
pip install -r requirements.txt
```
Create a `.env` file with `GEMINI_API_KEY=your_key_here`, then:
```bash
python main.py
```
Open http://127.0.0.1:8000. Without a key, only the rule-based fallback runs.

## Known limitations
- Volunteers come from a fixed sample file; there is no registration or database
- Tasks are free text; urgency is not modelled
- Gemini's free tier allows few requests per minute, so the fallback often answers when traffic is high
- Uses the older `google-generativeai` SDK, which Google has deprecated; migration to `google-genai` is planned
- No automated tests yet
