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

## Future Plans

**LRU Cache for Worktrees**

Keep N most recently used version checkouts around instead of eager cleanup. Evict oldest when full.

```python
from dmfv import versioned, configure

configure(cache_size=5)  # Keep up to 5 worktrees cached

async with versioned("./repos/bar", version="1.0.0") as bar:
    result = await bar.handler({})
# Worktree stays cached for reuse
```

**Registry**

Configure repos once at startup instead of passing paths everywhere.

```python
from dmfv import register, versioned

# At startup
register("bar", repo_path="./repos/bar")
register("baz", repo_path="./repos/baz")

# Later - just use the name
async with versioned("bar", version="1.0.0") as bar:
    result = await bar.handler({})
```
