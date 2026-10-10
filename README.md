# DMFV - Dynamically Managed Function Versions
This repo was created as a thought experiment and is not intended to be used in a real world application 

Run versioned Python functions in isolated subprocesses using git worktrees. Each version runs in complete isolation with automatic Pydantic validation.

## Features

- **Version Isolation**: Each request gets its own git worktree and subprocess
- **Concurrent Safe**: Multiple versions can run simultaneously without bleed
- **Typed Validation**: Automatic Pydantic model validation for inputs/outputs
- **Schema Introspection**: Extract JSON schemas from versioned functions

## Installation

```bash
pip install dmfv
```

Requires Python 3.11+ and pydantic>=2.0.

## Usage

```python
from dmfv import versioned

async with versioned("./repos/bar", version="1.0.0") as bar:
    # Call with dict - auto-validated against Pydantic model
    result = await bar.handler({"name": "test"})

    # Access schemas
    print(bar.schemas)
```

## Function Requirements

Functions must use Pydantic models for typed validation:

```python
# repos/bar/function.py
from pydantic import BaseModel

class Input(BaseModel):
    name: str
    count: int = 1

class Output(BaseModel):
    result: str
    version: str

def handler(data: Input) -> Output:
    return Output(result=f"Hello {data.name * data.count}", version="1.0.0")
```

Functions can also have no input (for parameterless handlers):

```python
def handler() -> Output:
    return Output(result="tick", version="3.0.0")
```

## Example

Run the example API:

```bash
cd example
./setup_repos.sh  # creates repo with 3 version tags
pip install fastapi uvicorn
uvicorn app.main:app --port 8765
```

Test different versions:

```bash
# v1.0.0 - basic input
curl 'http://localhost:8765/api/foo?version=1.0.0&name=test'
# {"result":"bar: test","version":"1.0.0"}

# v2.0.0 - with count parameter
curl 'http://localhost:8765/api/foo?version=2.0.0&name=test&count=3'
# {"result":"bat: testtesttest","version":"2.0.0"}

# v3.0.0 - no params, returns timestamp
curl 'http://localhost:8765/api/foo?version=3.0.0'
# {"result":"tick: 1234567890.123","version":"3.0.0","timestamp":1234567890.123}

# Get schemas for a version
curl 'http://localhost:8765/api/schemas?version=1.0.0'
```

Test concurrent isolation (with delay parameter):

```bash
# Run 3 versions concurrently with 2s delay each
curl 'http://localhost:8765/api/foo?version=1.0.0&name=v1&delay=2' &
curl 'http://localhost:8765/api/foo?version=2.0.0&name=v2&count=2&delay=2' &
curl 'http://localhost:8765/api/foo?version=3.0.0&delay=2' &
wait
# All complete in ~2s with correct isolated results
```

## How It Works

1. **Worktree Creation**: Creates a unique git worktree for the requested version
2. **Subprocess Spawn**: Launches isolated Python subprocess in that worktree
3. **RPC Communication**: Uses pickle-based RPC over stdin/stdout
4. **Schema Extraction**: Introspects Pydantic models for JSON schemas
5. **Validation**: Validates input dicts against extracted schemas
6. **Cleanup**: Removes worktree after request completes

## API Reference

### `versioned(repo_path, version, module_name="function", fallback=None)`

Async context manager for versioned module access.

- `repo_path`: Path to bare git repository
- `version`: Git tag to checkout
- `module_name`: Python module name (default: "function")
- `fallback`: Fallback version if requested version not found

### `ModuleProxy`

Returned by `versioned()` context manager.

- `proxy.handler(data)`: Call the handler function (async)
- `proxy.schemas`: Dict of function schemas with input/output JSON schemas

## Future Plans

**LRU Cache for Worktrees**

Keep N most recently used version checkouts around instead of eager cleanup.

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

# Later - just use the name
async with versioned("bar", version="1.0.0") as bar:
    result = await bar.handler({})
```
