from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
# Database initialization and seeding
from database import (
    initialize_database,
    list_sources,
    refresh_search_index,
    search_knowledge,
    seed_demo_data,
)
# ai connection
from ai_service import AIServiceError, generate_grounded_answer

BASE_DIRECTORY = Path(__file__).resolve().parent

app = FastAPI(title="Atlas")

initialize_database()
seed_demo_data()
refresh_search_index()

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIRECTORY / "static")),
    name="static",
)
templates = Jinja2Templates(
    directory=str(BASE_DIRECTORY / "templates")
)

class QuestionRequest(BaseModel):
    question: str
    role: str = "support"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )

@app.post("/api/ask")
def ask_question(request: QuestionRequest):
    matches = search_knowledge(
        question=request.question,
        role=request.role,
    )

    if not matches:
        return {
            "answer": (
                "I couldn't find an approved answer in the "
                "knowledge base for your access level."
            ),
            "sources": [],
            "mode": "no-match",
        }

    best_match = matches[0]

    try:
        answer = generate_grounded_answer(
            question=request.question,
            article=best_match,
        )
        response_mode = "ai"

    except AIServiceError as error:
        print(error)

        answer = best_match["excerpt"]
        response_mode = "retrieval-fallback"

    sources = [
        {
            "citation": f"S{index}",
            "title": source["title"],
            "type": source["source_type"],
            "location": source["source_location"],
        }
        for index, source in enumerate(
            best_match["sources"],
            start=1,
        )
    ]

    return {
        "answer": answer,
        "article": {
            "title": best_match["title"],
            "owner": best_match["owner"],
            "version": best_match["current_version"],
        },
        "sources": sources,
        "mode": response_mode,
    }

@app.get("/api/sources")
async def get_sources():
    return {
        "sources": list_sources()
    }