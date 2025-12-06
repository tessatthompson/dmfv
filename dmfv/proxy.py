"""Proxy module for versioned function execution."""
import asyncio
import pickle
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError, create_model

from dmfv.version_manager import VersionManager


RESERVED_FIELDS = {"version", "fallback"}


def _build_model_from_schema(schema: dict | None, name: str):
    """Build a dynamic Pydantic model from JSON schema."""
    if not schema:
        return None

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    type_map = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}

    fields = {}
    for field_name, field_schema in properties.items():
        field_type = type_map.get(field_schema.get("type"), Any)
        fields[field_name] = (field_type, ...) if field_name in required else (field_type, None)

    return create_model(name, **fields) if fields else None


async def _rpc_call(process, request: dict) -> dict:
    """Send RPC request and get response."""
    data = pickle.dumps(request)
    process.stdin.write(len(data).to_bytes(4, "big") + data)
    await process.stdin.drain()

    length = int.from_bytes(await process.stdout.readexactly(4), "big")
    return pickle.loads(await process.stdout.readexactly(length))


class FunctionProxy:
    """Proxy for a typed function with optional pre-validation."""

    def __init__(self, process: asyncio.subprocess.Process, name: str, input_schema: dict | None):
        self._process = process
        self._name = name
        self.input_schema = input_schema
        self._input_model = _build_model_from_schema(input_schema, f"{name}Input")

    def validate(self, data: dict) -> dict:
        """Pre-validate input data (optional). Strips reserved fields."""
        if not self._input_model:
            return data
        filtered = {k: v for k, v in data.items() if k not in RESERVED_FIELDS}
        return self._input_model.model_validate(filtered).model_dump()

    async def __call__(self, *args, **kwargs) -> Any:
        """Call the function via RPC."""
        response = await _rpc_call(self._process, {
            "action": "call",
            "func": self._name,
            "args": args,
            "kwargs": kwargs,
        })

        if response.get("error"):
            if response.get("validation_errors"):
                raise ValidationError.from_exception_data("Validation failed", response["validation_errors"])
            raise RuntimeError(response["error"])

        return response.get("result")


class ModuleProxy:
    """Proxy for a versioned module."""

    def __init__(self, process: asyncio.subprocess.Process, schemas: dict):
        self._process = process
        self._schemas = schemas
        self._functions = {
            name: FunctionProxy(process, name, info.get("input"))
            for name, info in schemas.items()
        }

    @property
    def schemas(self) -> dict:
        return self._schemas

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._functions:
            raise AttributeError(f"Function '{name}' not found")
        return self._functions[name]

    async def _close(self):
        """Shut down the subprocess."""
        try:
            await _rpc_call(self._process, {"action": "shutdown"})
        except Exception:
            pass

        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            self._process.kill()


class versioned:
    """Async context manager for versioned module access."""

    def __init__(self, repo_path: str | Path, version: str, module_name: str = "function", fallback: str | None = None):
        self.repo_path = Path(repo_path)
        self.version = version
        self.module_name = module_name
        self.fallback = fallback
        self._vm = None
        self._worktree = None
        self._proxy = None

    async def __aenter__(self) -> ModuleProxy:
        self._vm = VersionManager(
            repos_dir=self.repo_path.parent,
            worktrees_dir=self.repo_path.parent / ".worktrees",
        )
        self._worktree = self._vm.get_version_path(self.repo_path.name, self.version, fallback=self.fallback)

        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "dmfv.runner", str(self._worktree), self.module_name,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )

        try:
            ready = await process.stdout.readexactly(5)
        except asyncio.IncompleteReadError as e:
            stderr = await process.stderr.read()
            raise RuntimeError(f"Subprocess failed (incomplete read): {stderr.decode()}") from e
        if ready != b"READY":
            stderr = await process.stderr.read()
            raise RuntimeError(f"Subprocess failed to start: {stderr.decode()}")

        response = await _rpc_call(process, {"action": "get_schemas"})
        self._proxy = ModuleProxy(process, response.get("schemas", {}))
        return self._proxy

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._proxy:
            await self._proxy._close()
        if self._vm and self._worktree:
            self._vm.cleanup(self._worktree)
        return False
