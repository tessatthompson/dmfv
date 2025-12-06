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

def handler(body: dict) -> dict:
    """Returns 'bar'"""
    return {"result": "bar", "version": "1.0.0"}
EOF

git add function.py
git commit -m "v1.0.0: returns bar"
git tag 1.0.0

# Version 2.0.0 - returns "bat"
echo "Creating version 2.0.0 (returns 'bat')"
cat > function.py << 'EOF'
"""Bar function - Version 2.0.0"""

def handler(body: dict) -> dict:
    """Returns 'bat'"""
    return {"result": "bat", "version": "2.0.0"}
EOF

git add function.py
git commit -m "v2.0.0: returns bat"
git tag 2.0.0

# Push to bare repo
git push origin main --tags

# Cleanup temp directory
cd "$SCRIPT_DIR"
rm -rf "$TEMP_DIR"

echo ""
echo "Setup complete!"
echo ""
echo "Function repo created: $REPOS_DIR/bar"
echo "  - Version 1.0.0: returns 'bar'"
echo "  - Version 2.0.0: returns 'bat'"
echo ""
echo "To start the example server:"
echo "  cd example"
echo "  pip install -e .."
echo "  pip install fastapi uvicorn"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Then test with:"
echo "  curl -X POST 'http://localhost:8000/api/foo?version=1.0.0'"
echo "  curl -X POST 'http://localhost:8000/api/foo?version=2.0.0'"
