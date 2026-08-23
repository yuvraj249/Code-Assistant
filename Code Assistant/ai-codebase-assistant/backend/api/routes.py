"""
API Routes — All FastAPI endpoints for CodeMind
Includes: ingest, chat, stream, summary, repos management, and agent endpoint.
"""

import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
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

# ─── Request / Response Models ────────────────────────────────────────────────

class GithubRepoRequest(BaseModel):
    github_url: str
    branch: Optional[str] = "main"

class QuestionRequest(BaseModel):
    question: str
    repo_id: Optional[str] = None
    mode: Optional[str] = "explain"  # explain | bugs | tests | architecture

class AgentRequest(BaseModel):
    """OpenAI Function Calling compatible agent request."""
    question: str
    repo_id: Optional[str] = None
    mode: Optional[str] = "explain"
    top_k: Optional[int] = 8
    return_citations: Optional[bool] = True


# ─── Ingestion Endpoints ──────────────────────────────────────────────────────

@router.post("/upload-repo", tags=["Ingestion"])
async def upload_repo(file: UploadFile = File(...)):
    """
    Accept a ZIP file of a local repository, extract, parse, embed, and store in ChromaDB.
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
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:
            raise HTTPException(500, f"Ingestion failed: {str(e)}")


@router.post("/load-github-repo", tags=["Ingestion"])
async def load_github_repo(request: GithubRepoRequest):
    """
    Clone a public GitHub repository, parse, embed, and store in ChromaDB.
    """
    try:
        result = await ingestion_service.ingest_github(request.github_url, request.branch)
        return JSONResponse({"status": "success", **result})
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"GitHub clone failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"GitHub ingestion failed: {str(e)}")


# ─── Chat Endpoints ───────────────────────────────────────────────────────────

@router.post("/ask-question", tags=["Chat"])
async def ask_question(request: QuestionRequest):
    """
    Hybrid Q&A pipeline:
    - If repo_id is provided & indexed: RAG retrieval over repo.
    - If no repo_id: Conversational AI coding assistant mode.
    """
    try:
        result = await rag_service.answer(
            question=request.question,
            repo_id=request.repo_id,
            mode=request.mode,
        )
        return JSONResponse({"status": "success", **result})
    except Exception as e:
        raise HTTPException(500, f"Q&A query failed: {str(e)}")


@router.post("/stream-answer", tags=["Chat"])
async def stream_answer(request: QuestionRequest):
    """
    SSE streaming answer — tokens arrive in real-time from the LLM.
    Works with or without a loaded repository.
    """
    async def event_generator():
        try:
            async for token in rag_service.stream_answer(
                question=request.question,
                repo_id=request.repo_id,
                mode=request.mode,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Agent Endpoint ───────────────────────────────────────────────────────────

@router.post("/agent", tags=["Agent"])
async def agent_endpoint(request: AgentRequest):
    """
    OpenAI Function Calling / tool-use compatible agent endpoint.
    Returns structured JSON with answer, citations, and metadata.
    Call this from LangGraph, Claude tools, or any AI pipeline.

    Example curl (without repo):
        curl -X POST http://localhost:8000/api/agent \\
          -H "Content-Type: application/json" \\
          -d '{"question": "How do I implement JWT in FastAPI?", "mode": "explain"}'
    """
    try:
        result = await rag_service.answer(
            question=request.question,
            repo_id=request.repo_id,
            mode=request.mode,
        )
        return JSONResponse({
            "status": "success",
            "agent": "codemind-v2",
            "request": {
                "question": request.question,
                "repo_id": request.repo_id,
                "mode": request.mode,
            },
            "response": {
                "answer": result["answer"],
                "citations": result.get("citations", []) if request.return_citations else [],
                "has_context": result.get("has_context", False),
                "mode": result["mode"],
                "model": result.get("model", "gpt-4o-mini"),
            },
        })
    except Exception as e:
        raise HTTPException(500, f"Agent query failed: {str(e)}")


# ─── Repo Management Endpoints ────────────────────────────────────────────────

@router.get("/repos", tags=["Repos"])
async def list_repos():
    """List all indexed repositories (persisted across restarts)."""
    try:
        repos = ingestion_service.list_repos()
        return JSONResponse({"status": "success", "repos": repos})
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/repos/{repo_id}", tags=["Repos"])
async def delete_repo(repo_id: str):
    """Delete a repo from the registry and remove its ChromaDB collection."""
    try:
        ingestion_service.delete_repo(repo_id)
        summary_service.invalidate_cache(repo_id)
        return JSONResponse({"status": "success", "message": f"Repo '{repo_id}' deleted."})
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/repo-summary/{repo_id}", tags=["Repos"])
async def get_repo_summary(repo_id: str):
    """
    Return AI-generated repo summary including:
    - Language, architecture, modules, key files, dependencies
    - LLM-generated Mermaid architecture diagram
    """
    try:
        summary = await summary_service.get_summary(repo_id)
        return JSONResponse({"status": "success", "summary": summary})
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Summary generation failed: {str(e)}")
