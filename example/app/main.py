"""
Example FastAPI application using DMFV (Dynamically Managed Function Versions).

Usage:
    uvicorn app.main:app --reload

Endpoints:
    GET  /api/foo?version=1.0.0&name=test       - Calls bar function at version 1.0.0
    GET  /api/foo?version=2.0.0&name=test       - Calls bar function at version 2.0.0
    GET  /api/foo?version=3.0.0                 - Calls bar function at version 3.0.0 (no params)
    POST /api/foo?version=1.0.0                 - Calls bar function with request body
    GET  /api/schemas?version=1.0.0             - Get schemas for a version

    Use &delay=N to add N seconds delay (for concurrent testing)
"""
import asyncio
from pathlib import Path

from fastapi import FastAPI, Query, Request, HTTPException

from dmfv import versioned

# Path to repos directory (resolve to absolute path)
BASE_DIR = Path(__file__).parent.parent.resolve()
REPOS_DIR = BASE_DIR / "repos"

# Reserved fields stripped before passing to handler
RESERVED_FIELDS = {"version", "fallback", "delay"}

app = FastAPI(
    title="Example DMFV API",
    description="Example API using DMFV with typed validation",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/schemas")
async def get_schemas(version: str = Query(..., description="Version tag")):
    """Get schemas for a specific version."""
    try:
        async with versioned(REPOS_DIR / "bar", version=version) as bar:
            return {
                "version": version,
                "schemas": bar.schemas,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route("/api/foo", methods=["GET", "POST"])
async def execute_foo(
    request: Request,
    version: str = Query(..., description="Version tag to execute"),
    delay: float = Query(0, description="Delay in seconds (for testing concurrency)"),
):
    """Execute foo function at a specific version.

    Merges query params and body (body wins on conflicts).
    Reserved fields (version, fallback, delay) are stripped automatically.
    """
    # Get query params
    query_params = dict(request.query_params)

    # Get body for POST requests
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            pass

    # Merge: body wins on conflicts, strip reserved fields
    raw = {k: v for k, v in {**query_params, **body}.items() if k not in RESERVED_FIELDS}

    try:
        async with versioned(REPOS_DIR / "bar", version=version) as bar:
            # Optional delay for testing concurrent isolation (simulates process lag)
            if delay > 0:
                await asyncio.sleep(delay)

            # Call handler - pass raw if non-empty, otherwise no args (for v3.0.0)
            if raw:
                result = await bar.handler(raw)
            else:
                result = await bar.handler()
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
