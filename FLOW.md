# DMFV Execution Flow

```
User Code                    proxy.py                 runner.py              Git
    │                           │                         │                    │
    │  async with versioned()   │                         │                    │
    │ ─────────────────────────>│                         │                    │
    │                           │                         │                    │
    │                           │ get_version_path()      │                    │
    │                           │ ───────────────────────────────────────────> │
    │                           │                         │   git worktree add │
    │                           │ <─────────────────────────────────────────── │
    │                           │  worktree_path          │                    │
    │                           │                         │                    │
    │                           │ create_subprocess_exec  │                    │
    │                           │ ──────────────────────> │                    │
    │                           │                         │ load_module()      │
    │                           │                         │ stdout.write(READY)│
    │                           │ <────────────────────── │                    │
    │                           │        b"READY"         │                    │
    │                           │                         │                    │
    │  await bar.handler({})    │                         │                    │
    │ ─────────────────────────>│                         │                    │
    │                           │ pickle({action: call})  │                    │
    │                           │ ──────────────────────> │                    │
    │                           │                         │ func(*args)        │
    │                           │ pickle({result: ...})   │                    │
    │                           │ <────────────────────── │                    │
    │ <─────────────────────────│                         │                    │
    │         result            │                         │                    │
    │                           │                         │                    │
    │  context exit             │                         │                    │
    │ ─────────────────────────>│                         │                    │
    │                           │ pickle({action: shutdown})                   │
    │                           │ ──────────────────────> │                    │
    │                           │ process.terminate()     │ exits              │
    │                           │                         │                    │
    │                           │ cleanup(worktree)       │                    │
    │                           │ ───────────────────────────────────────────> │
    │                           │                         │  git worktree remove
```
