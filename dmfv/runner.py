"""
Subprocess runner for versioned module execution.

Loads a module from a worktree and handles pickle-based RPC calls.

Usage: python -m dmfv.runner <worktree_path> <module_name>
"""
import asyncio
import importlib.util
import inspect
import pickle
import sys
import traceback
from pathlib import Path


def load_module(worktree_path: str, module_name: str):
    """Load a module from the worktree path."""
    module_path = Path(worktree_path) / f"{module_name}.py"

    if not module_path.exists():
        raise ImportError(f"Module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def read_message(stdin) -> dict:
    """Read a length-prefixed pickle message from stdin."""
    length_bytes = stdin.read(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    data = stdin.read(length)
    return pickle.loads(data)


def write_message(stdout, data: dict):
    """Write a length-prefixed pickle message to stdout."""
    encoded = pickle.dumps(data)
    stdout.write(len(encoded).to_bytes(4, "big"))
    stdout.write(encoded)
    stdout.flush()


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m dmfv.runner <worktree_path> <module_name>", file=sys.stderr)
        sys.exit(1)

    worktree_path = sys.argv[1]
    module_name = sys.argv[2]

    # Use binary mode for stdin/stdout
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    try:
        module = load_module(worktree_path, module_name)
    except Exception as e:
        print(f"Failed to load module: {e}", file=sys.stderr)
        sys.exit(1)

    # Signal ready
    stdout.write(b"READY")
    stdout.flush()

    # Main loop - handle calls
    while True:
        try:
            request = read_message(stdin)
            if request is None:
                break

            action = request.get("action")

            if action == "shutdown":
                break

            if action == "call":
                func_name = request["func"]
                args = request.get("args", ())
                kwargs = request.get("kwargs", {})

                try:
                    func = getattr(module, func_name)
                    result = func(*args, **kwargs)
                    # Handle async functions
                    if inspect.iscoroutine(result):
                        result = asyncio.run(result)
                    write_message(stdout, {"result": result})
                except Exception as e:
                    write_message(stdout, {
                        "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                    })

        except Exception as e:
            # Protocol error - try to report and continue
            try:
                write_message(stdout, {"error": f"Protocol error: {e}"})
            except Exception:
                break


if __name__ == "__main__":
    main()
