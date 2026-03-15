from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ingest, quiz, answers, search

app = FastAPI(
    title="Peblo Quiz Engine",
    description="AI-powered content ingestion and adaptive quiz generation platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(quiz.router, tags=["Quiz"])
app.include_router(answers.router, tags=["Answers"])
app.include_router(search.router, tags=["RAG Search"])

app.mount("/", StaticFiles(directory="static", html=True), name="static")
