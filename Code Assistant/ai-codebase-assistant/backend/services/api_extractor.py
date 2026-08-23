"""
API Extractor Service
Scans code chunks in a repository to extract API endpoints (FastAPI, Express, Flask, Gin, Next.js, Django).
Extracts: HTTP Method, Route Path, Function Name, File Path, and inferred parameters.
"""

import re
from typing import List, Dict, Any
from core.vector_store import VectorStore

vector_store = VectorStore()

# RegEx patterns for common frameworks
ROUTE_PATTERNS = [
    # FastAPI / Flask: @app.get("/users"), @router.post("/login")
    (r'@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']', "python"),
    # Express.js / Node: app.get('/users', ...), router.post('/login', ...)
    (r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', "javascript"),
    # Go (Gin / Fiber): r.GET("/users", ...), api.POST("/login", ...)
    (r'\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*["\']([^"\']+)["\']', "go"),
    # Next.js / Spring annotation style
    (r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping)\s*\(\s*["\']([^"\']+)["\']', "java"),
]


class APIExtractorService:

    def extract_endpoints(self, repo_id: str) -> List[Dict[str, Any]]:
        """
        Scan all indexed chunks for repo_id and extract detected API endpoints.
        """
        collection = vector_store.get_or_create_collection(repo_id)
        results = collection.get(include=["documents", "metadatas"])

        if not results or not results.get("documents"):
            return []

        endpoints = []
        seen = set()

        for doc, meta in zip(results["documents"], results["metadatas"]):
            file_path = meta.get("file_path", "")
            language = meta.get("language", "")

            for pattern, lang in ROUTE_PATTERNS:
                matches = re.findall(pattern, doc, re.IGNORECASE)
                for match in matches:
                    method = match[0].upper()
                    path = match[1]

                    key = f"{method}:{path}"
                    if key in seen:
                        continue
                    seen.add(key)

                    endpoints.append({
                        "method": method,
                        "path": path,
                        "file_path": file_path,
                        "language": language,
                        "function_name": meta.get("function_name", ""),
                        "sample_body": self._generate_sample_body(method, path, doc),
                        "headers": {"Content-Type": "application/json"} if method in ["POST", "PUT", "PATCH"] else {},
                    })

        return sorted(endpoints, key=lambda x: (x["path"], x["method"]))

    def _generate_sample_body(self, method: str, path: str, doc_snippet: str) -> str:
        """Infer a sample JSON payload body based on route name & code snippet."""
        if method not in ["POST", "PUT", "PATCH"]:
            return ""

        if "login" in path.lower() or "auth" in path.lower():
            return '{\n  "email": "user@example.com",\n  "password": "password123"\n}'
        elif "user" in path.lower() or "register" in path.lower():
            return '{\n  "username": "johndoe",\n  "email": "john@example.com",\n  "role": "user"\n}'
        elif "product" in path.lower() or "item" in path.lower():
            return '{\n  "name": "Sample Product",\n  "price": 49.99,\n  "category": "Electronics"\n}'
        
        return '{\n  "key": "value"\n}'
