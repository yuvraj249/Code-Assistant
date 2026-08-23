"""
API Routes — All FastAPI endpoints for CodeMind
Includes: ingest, chat, stream, summary, repos management, agent endpoint,
and NEW Interactive API Tester / Proxy endpoint.
"""

import json
import time
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import shutil
import tempfile
import os

from services.ingestion_service import IngestionService
from services.rag_service import RAGService
from services.summary_service import SummaryService
from services.api_extractor import APIExtractorService

router = APIRouter()
ingestion_service = IngestionService()
rag_service = RAGService()
summary_service = SummaryService()
api_extractor = APIExtractorService()

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

class ProxyApiRequest(BaseModel):
    """Interactive API Tester Request payload."""
    method: str
    url: str
    headers: Optional[Dict[str, str]] = {}
    body: Optional[str] = None


# ─── Ingestion Endpoints ──────────────────────────────────────────────────────

@router.post("/upload-repo", tags=["Ingestion"])
async def upload_repo(file: UploadFile = File(...)):
    """Accept a ZIP file of a local repository, extract, parse, embed, and store in ChromaDB."""
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
    """Clone a public GitHub repository, parse, embed, and store in ChromaDB."""
    try:
        result = await ingestion_service.ingest_github(request.github_url, request.branch)
        return JSONResponse({"status": "success", **result})
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"GitHub clone failed: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"GitHub ingestion failed: {str(e)}")


# ─── Chat & Agent Endpoints ───────────────────────────────────────────────────

@router.post("/ask-question", tags=["Chat"])
async def ask_question(request: QuestionRequest):
    """RAG or Conversational Q&A pipeline."""
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
    """SSE streaming answer generator."""
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent", tags=["Agent"])
async def agent_endpoint(request: AgentRequest):
    """OpenAI Function Calling / tool-use compatible agent endpoint."""
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
                "model": result.get("model", "gemini-3.6-flash"),
            },
        })
    except Exception as e:
        raise HTTPException(500, f"Agent query failed: {str(e)}")


# ─── API Tester & Playground Endpoints ───────────────────────────────────────

@router.get("/repo-endpoints/{repo_id}", tags=["API Tester"])
async def get_repo_endpoints(repo_id: str):
    """Scan the repository and return all detected REST API endpoints."""
    try:
        endpoints = api_extractor.extract_endpoints(repo_id)
        return JSONResponse({"status": "success", "repo_id": repo_id, "endpoints": endpoints})
    except Exception as e:
        raise HTTPException(500, f"Failed to extract endpoints: {str(e)}")


@router.post("/proxy-request", tags=["API Tester"])
async def proxy_api_request(request: ProxyApiRequest):
    """
    Execute an HTTP request to any endpoint on behalf of the UI (Postman feature).
    Returns status code, response timing (ms), response body, and response headers.
    """
    start_time = time.time()
    method = request.method.upper()

    # Parse JSON body if present
    json_payload = None
    if request.body and request.body.strip():
        try:
            json_payload = json.loads(request.body)
        except Exception:
            json_payload = request.body

    headers = request.headers or {}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if json_payload and isinstance(json_payload, dict):
                res = await client.request(method, request.url, headers=headers, json=json_payload)
            else:
                res = await client.request(method, request.url, headers=headers, content=request.body)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            # Try parsing response as JSON
            try:
                response_data = res.json()
            except Exception:
                response_data = res.text

            return JSONResponse({
                "status": "success",
                "status_code": res.status_code,
                "elapsed_ms": elapsed_ms,
                "headers": dict(res.headers),
                "data": response_data,
            })
    except Exception as e:
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return JSONResponse({
            "status": "error",
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "error": f"Failed to connect to {request.url}: {str(e)}",
        }, status_code=502)


# ─── Repo Management Endpoints ────────────────────────────────────────────────

@router.get("/repos", tags=["Repos"])
async def list_repos():
    """List all indexed repositories."""
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
    """Return AI-generated repo summary & Mermaid diagram."""
    try:
        summary = await summary_service.get_summary(repo_id)
        return JSONResponse({"status": "success", "summary": summary})
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Summary generation failed: {str(e)}")
