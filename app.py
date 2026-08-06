from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
# Database initialization and seeding
from database import initialize_database, list_sources, seed_demo_data

BASE_DIRECTORY = Path(__file__).resolve().parent

app = FastAPI(title="Atlas")

initialize_database()

seed_demo_data()
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIRECTORY / "static")),
    name="static",
)
templates = Jinja2Templates(
    directory=str(BASE_DIRECTORY / "templates")
)

class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.post("/api/ask")
async def ask_question(payload: QuestionRequest):
    return {
        "title": "The return period is 14 calendar days.",
        "answer": (
            "Customers in Malaysia can return company-issued "
            "hardware within 14 calendar days of receipt."
        ),
        "sources": [
            "Hardware Returns Policy",
            "Malaysia Returns Addendum",
        ],
    }

@app.get("/api/sources")
async def get_sources():
    return {
        "sources": list_sources()
    }