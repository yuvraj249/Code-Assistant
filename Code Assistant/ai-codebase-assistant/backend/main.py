"""
AI Codebase Assistant - FastAPI Backend
Main application entry point
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
import uvicorn

app = FastAPI(
    title="CodeMind — AI Codebase Assistant",
    description="RAG-powered developer tool for understanding codebases. Also exposes an agent-compatible /api/agent endpoint.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGIN",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    api_key_set = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "status": "ok",
        "version": "2.0.0",
        "openai_key_configured": api_key_set,
    }


@app.on_event("startup")
async def startup_event():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("\n⚠  WARNING: OPENAI_API_KEY is not set. AI answers will not work.")
        print("   Add it to backend/.env:  OPENAI_API_KEY=sk-...\n")
    else:
        print(f"✓  OpenAI API key configured ({key[:8]}...)")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
