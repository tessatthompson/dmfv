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
import typing
from pathlib import Path

from pydantic import BaseModel, ValidationError


RESERVED_FIELDS = {"version", "fallback"}


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


def read_message(stdin) -> dict | None:
    """Read a length-prefixed pickle message from stdin."""
    length_bytes = stdin.read(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, "big")
    return pickle.loads(stdin.read(length))


def write_message(stdout, data: dict):
    """Write a length-prefixed pickle message to stdout."""
    encoded = pickle.dumps(data)
    stdout.write(len(encoded).to_bytes(4, "big") + encoded)
    stdout.flush()


def get_func_type_info(func) -> dict | None:
    """Extract Pydantic type info from a function. Returns None if not typed."""
    try:
        hints = typing.get_type_hints(func)
        params = list(inspect.signature(func).parameters.values())
    except Exception:
        return None

    input_type = None
    if params:
        t = hints.get(params[0].name)
        if isinstance(t, type) and issubclass(t, BaseModel):
            input_type = t

    output_type = hints.get("return")
    if not (isinstance(output_type, type) and issubclass(output_type, BaseModel)):
        output_type = None

    if not input_type and not output_type:
        return None

    return {"input": input_type, "output": output_type}


def get_module_functions(module) -> dict:
    """Get all typed functions from a module with their type info."""
    funcs = {}
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and inspect.isfunction(obj):
            type_info = get_func_type_info(obj)
            if type_info:
                funcs[name] = type_info
    return funcs


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m dmfv.runner <worktree_path> <module_name>", file=sys.stderr)
        sys.exit(1)

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer

    try:
        module = load_module(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"Failed to load module: {e}", file=sys.stderr)
        sys.exit(1)

    # Cache typed functions
    func_types = get_module_functions(module)

    stdout.write(b"READY")
    stdout.flush()

    while True:
        try:
            request = read_message(stdin)
            if request is None:
                break

            action = request.get("action")

            if action == "shutdown":
                break

            if action == "get_schemas":
                schemas = {
                    name: {
                        k: t.model_json_schema()
                        for k, t in info.items() if t
                    }
                    for name, info in func_types.items()
                }
                write_message(stdout, {"schemas": schemas})
                continue

            if action == "call":
                func_name = request["func"]
                args = request.get("args", ())
                kwargs = request.get("kwargs", {})

                try:
                    func = getattr(module, func_name)
                    type_info = func_types.get(func_name, {})

                    # Validate and convert input
                    input_type = type_info.get("input")
                    if input_type and args and isinstance(args[0], dict):
                        filtered = {k: v for k, v in args[0].items() if k not in RESERVED_FIELDS}
                        args = (input_type.model_validate(filtered),) + args[1:]

                    result = func(*args, **kwargs)

                    # Handle async
                    if inspect.iscoroutine(result):
                        result = asyncio.run(result)

                    # Serialize BaseModel to dict
                    if isinstance(result, BaseModel):
                        result = result.model_dump()

                    write_message(stdout, {"result": result})

                except ValidationError as e:
                    write_message(stdout, {
                        "error": f"ValidationError: {e}",
                        "validation_errors": e.errors(),
                    })
                except Exception as e:
                    write_message(stdout, {
                        "error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                    })

        except Exception as e:
            try:
                write_message(stdout, {"error": f"Protocol error: {e}"})
            except Exception:
                break


if __name__ == "__main__":
    main()
