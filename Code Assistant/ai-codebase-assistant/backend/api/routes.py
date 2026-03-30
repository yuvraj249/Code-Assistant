"""
API Routes - All FastAPI endpoints for the Codebase Assistant
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import shutil
import tempfile
import os

from services.ingestion_service import IngestionService
from services.rag_service import RAGService
from services.summary_service import SummaryService

router = APIRouter()
ingestion_service = IngestionService()
rag_service = RAGService()
summary_service = SummaryService()

# ─── Request Models ───────────────────────────────────────────────────────────

class GithubRepoRequest(BaseModel):
    github_url: str
    branch: Optional[str] = "main"

class QuestionRequest(BaseModel):
    question: str
    repo_id: str
    mode: Optional[str] = "explain"  # explain | bugs | tests | architecture


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/upload-repo")
async def upload_repo(file: UploadFile = File(...)):
    """
    Accept a ZIP file of a local repository, extract it,
    parse + chunk + embed all code files, store in ChromaDB.
    """
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "Only .zip archives are supported")

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "repo.zip")
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            result = await ingestion_service.ingest_zip(zip_path, tmpdir)
            return JSONResponse({"status": "success", **result})
        except Exception as e:
            raise HTTPException(500, f"Ingestion failed: {str(e)}")


@router.post("/load-github-repo")
async def load_github_repo(request: GithubRepoRequest):
    """
    Clone a public GitHub repository, parse + chunk + embed,
    store in ChromaDB.
    """
    try:
        result = await ingestion_service.ingest_github(
            request.github_url, request.branch
        )
        return JSONResponse({"status": "success", **result})
    except Exception as e:
        raise HTTPException(500, f"GitHub ingestion failed: {str(e)}")


@router.post("/ask-question")
async def ask_question(request: QuestionRequest):
    """
    RAG pipeline:
    1. Embed question
    2. Vector search ChromaDB
    3. Retrieve top-k chunks
    4. Send context + question to LLM
    5. Return answer
    """
    try:
        answer = await rag_service.answer(
            question=request.question,
            repo_id=request.repo_id,
            mode=request.mode
        )
        return JSONResponse({"status": "success", "answer": answer})
    except Exception as e:
        raise HTTPException(500, f"RAG query failed: {str(e)}")


@router.get("/repo-summary/{repo_id}")
async def get_repo_summary(repo_id: str):
    """
    Return cached or freshly generated repo summary including:
    - Language, architecture, modules, key files, dependencies
    - Mermaid architecture diagram
    """
    try:
        summary = await summary_service.get_summary(repo_id)
        return JSONResponse({"status": "success", "summary": summary})
    except Exception as e:
        raise HTTPException(500, f"Summary generation failed: {str(e)}")


@router.get("/repos")
async def list_repos():
    """List all indexed repositories."""
    try:
        repos = ingestion_service.list_repos()
        return JSONResponse({"status": "success", "repos": repos})
    except Exception as e:
        raise HTTPException(500, str(e))
