"""Proxy module for versioned function execution."""
import asyncio
import pickle
import sys
from pathlib import Path

from dmfv.version_manager import VersionManager


class ModuleProxy:
    """Proxy object that forwards attribute access as subprocess calls."""

    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        async def call(*args, **kwargs):
            request = pickle.dumps({"action": "call", "func": name, "args": args, "kwargs": kwargs})
            self._process.stdin.write(len(request).to_bytes(4, "big") + request)
            await self._process.stdin.drain()

            length = int.from_bytes(await self._process.stdout.readexactly(4), "big")
            response = pickle.loads(await self._process.stdout.readexactly(length))

            if response.get("error"):
                raise RuntimeError(response["error"])
            return response.get("result")

        return call

    async def _close(self):
        """Shut down the subprocess."""
        try:
            request = pickle.dumps({"action": "shutdown"})
            self._process.stdin.write(len(request).to_bytes(4, "big") + request)
            await self._process.stdin.drain()
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

        ready = await process.stdout.readexactly(5)
        if ready != b"READY":
            stderr = await process.stderr.read()
            raise RuntimeError(f"Subprocess failed to start: {stderr.decode()}")

        self._proxy = ModuleProxy(process)
        return self._proxy

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._proxy:
            await self._proxy._close()
        if self._vm and self._worktree:
            self._vm.cleanup(self._worktree)
        return False
