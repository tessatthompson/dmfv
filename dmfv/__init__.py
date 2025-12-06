"""
DMFV - Dynamically Managed Function Versions

Simple interface for running versioned Python modules in isolated subprocesses.

Usage:
    from dmfv import versioned

    async with versioned("./repos/mymodule", version="1.0.0") as mymodule:
        result = await mymodule.handler(data)
"""
from dmfv.proxy import versioned

__all__ = ["versioned"]
