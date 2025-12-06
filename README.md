# DMFV - Dynamically Managed Function Versions

Run versioned Python functions in isolated subprocesses using git worktrees.

## Installation

```bash
pip install git+https://github.com/mantacares/dmfv.git@v0.1.0
```

## Usage

```python
from dmfv import versioned

async with versioned("./repos/mymodule", version="1.0.0") as mymodule:
    result = await mymodule.handler(data)
```

## Requirements

The target module must be a **git repository with version tags**:

```
repos/mymodule/
├── .git/
└── function.py   # must contain a `handler(data)` function
```

Create versions using git tags:
```bash
git tag -a 1.0.0 -m "v1.0.0"
git tag -a 2.0.0 -m "v2.0.0"
```

## Example

Run the example API:

```bash
cd example
./setup_repos.sh  # creates example repo with version tags
pip install fastapi uvicorn
uvicorn app.main:app --port 8765
```

Test:
```bash
curl 'http://localhost:8765/api/foo?version=1.0.0'
curl 'http://localhost:8765/api/foo?version=2.0.0'
```
