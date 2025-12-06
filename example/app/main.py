"""
Example FastAPI application using DMFV (Dynamically Managed Function Versions).

Usage:
    uvicorn app.main:app --reload

Endpoints:
    GET  /api/foo?version=1.0.0       - Calls bar function at version 1.0.0
    GET  /api/foo?version=2.0.0       - Calls bar function at version 2.0.0
    POST /api/foo-post?version=1.0.0  - Calls bar function with request body
"""
from pathlib import Path

from fastapi import FastAPI, Query, Request, HTTPException

from dmfv import versioned

# Path to repos directory
BASE_DIR = Path(__file__).parent.parent
REPOS_DIR = BASE_DIR / "repos"

app = FastAPI(
    title="Example DMFV API",
    description="Example API using DMFV",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/foo")
async def execute_foo(version: str = Query(..., description="Version tag to execute")):
    """Execute foo function at a specific version. Falls back to newest if not found."""
    try:
        async with versioned(REPOS_DIR / "bar", version=version) as bar:
            result = await bar.handler({})
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/foo-post")
async def execute_foo_post(
    request: Request,
    version: str = Query(..., description="Version tag to execute"),
):
    """Execute foo function at a specific version with request body."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        async with versioned(REPOS_DIR / "bar", version=version) as bar:
            result = await bar.handler(body)
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
