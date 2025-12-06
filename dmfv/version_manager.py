import shutil
import subprocess
import uuid
from pathlib import Path


class VersionManager:
    """Manages git worktrees for versioned function execution."""

    def __init__(self, repos_dir: Path, worktrees_dir: Path):
        self.repos_dir = repos_dir
        self.worktrees_dir = worktrees_dir
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def list_tags(self, func_name: str) -> list[str]:
        """List all tags in the function's repo."""
        repo_path = self.repos_dir / func_name
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {func_name}")

        result = subprocess.run(
            ["git", "tag", "-l"], cwd=repo_path,
            capture_output=True, text=True, check=True,
        )
        return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]

    def get_version_path(self, func_name: str, version: str, fallback: str | None = None) -> Path:
        """Create a worktree at the requested version. Returns worktree path."""
        repo_path = self.repos_dir / func_name
        tags = self.list_tags(func_name)

        # Resolve version
        if version not in tags:
            if fallback and fallback in tags:
                version = fallback
            elif tags:
                version = sorted(tags, reverse=True)[0]  # newest
            else:
                raise ValueError(f"No tags found for {func_name}")

        # Create worktree
        worktree_path = self.worktrees_dir / f"{func_name}_{version}_{uuid.uuid4().hex[:8]}"
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), version],
            cwd=repo_path, capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {result.stderr.decode()}")
        return worktree_path

    def cleanup(self, worktree_path: Path) -> None:
        """Remove a worktree after execution."""
        if not worktree_path.exists():
            return

        func_name = worktree_path.name.rsplit("_", 2)[0]
        repo_path = self.repos_dir / func_name

        if repo_path.exists():
            subprocess.run(
                ["git", "worktree", "remove", str(worktree_path), "--force"],
                cwd=repo_path, capture_output=True,
            )

        if worktree_path.exists():
            shutil.rmtree(worktree_path)
