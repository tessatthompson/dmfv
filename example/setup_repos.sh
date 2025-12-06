#!/bin/bash
# Setup script for example function repos
# Creates the 'bar' function repo with two versions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_DIR="$SCRIPT_DIR/repos"
TEMP_DIR="$SCRIPT_DIR/.temp_setup"

echo "Setting up example function repos..."

# Clean up any existing setup
rm -rf "$REPOS_DIR/bar"
rm -rf "$TEMP_DIR"

# Create repos directory
mkdir -p "$REPOS_DIR"

# Create bare repo for 'bar' function
echo "Creating bare repo: bar"
mkdir -p "$REPOS_DIR/bar"
git init --bare "$REPOS_DIR/bar"

# Create temp working directory
mkdir -p "$TEMP_DIR"
git clone "$REPOS_DIR/bar" "$TEMP_DIR/bar"
cd "$TEMP_DIR/bar"

# Configure git for commits (local to this repo)
git config user.email "example@example.com"
git config user.name "Example"
git config commit.gpgsign false
git config tag.gpgsign false

# Version 1.0.0 - returns "bar"
echo "Creating version 1.0.0 (returns 'bar')"
cat > function.py << 'EOF'
"""Bar function - Version 1.0.0"""
from pydantic import BaseModel


class Input(BaseModel):
    name: str


class Output(BaseModel):
    result: str
    version: str


def handler(data: Input) -> Output:
    """Returns 'bar' with the input name."""
    return Output(result=f"bar: {data.name}", version="1.0.0")
EOF

git add function.py
git commit -m "v1.0.0: returns bar"
git tag 1.0.0

# Version 2.0.0 - returns "bat"
echo "Creating version 2.0.0 (returns 'bat')"
cat > function.py << 'EOF'
"""Bar function - Version 2.0.0"""
from pydantic import BaseModel


class Input(BaseModel):
    name: str
    count: int = 1


class Output(BaseModel):
    result: str
    version: str


def handler(data: Input) -> Output:
    """Returns 'bat' with the input name repeated."""
    return Output(result=f"bat: {data.name * data.count}", version="2.0.0")
EOF

git add function.py
git commit -m "v2.0.0: returns bat"
git tag 2.0.0

# Version 3.0.0 - no params, returns timestamp
echo "Creating version 3.0.0 (no params, returns timestamp)"
cat > function.py << 'EOF'
"""Bar function - Version 3.0.0"""
import time
from pydantic import BaseModel


class Output(BaseModel):
    result: str
    version: str
    timestamp: float


def handler() -> Output:
    """Returns timestamp with no input required."""
    ts = time.time()
    return Output(result=f"tick: {ts}", version="3.0.0", timestamp=ts)
EOF

git add function.py
git commit -m "v3.0.0: no params, returns timestamp"
git tag 3.0.0

# Push to bare repo
git push origin main --tags

# Cleanup temp directory
cd "$SCRIPT_DIR"
rm -rf "$TEMP_DIR"

echo ""
echo "Setup complete!"
echo ""
echo "Function repo created: $REPOS_DIR/bar"
echo "  - Version 1.0.0: Input{name: str} -> Output{result, version}"
echo "  - Version 2.0.0: Input{name: str, count: int} -> Output{result, version}"
echo "  - Version 3.0.0: (no input) -> Output{result, version, timestamp}"
echo ""
echo "To start the example server:"
echo "  cd example"
echo "  pip install -e .."
echo "  pip install fastapi uvicorn"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Then test with:"
echo "  curl 'http://localhost:8000/api/foo?version=1.0.0&name=test'"
echo "  curl 'http://localhost:8000/api/foo?version=2.0.0&name=test&count=3'"
echo "  curl 'http://localhost:8000/api/foo?version=3.0.0'"
echo "  curl 'http://localhost:8000/api/foo?version=1.0.0&name=test&delay=2'  # 2 second delay"
