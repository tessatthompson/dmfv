# DMFV - Dynamically Managed Function Versions

Run versioned Python functions in isolated subprocesses using git worktrees.

## Installation

```bash
pip install git+https://github.com/YOUR_USERNAME/dmfv.git@v0.1.0
```

## Usage

```python
from dmfv import versioned

async with versioned("./repos/mymodule", version="1.0.0") as mymodule:
    result = await mymodule.handler(data)
```
