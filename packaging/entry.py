"""Frozen Windows entry. CUDA PATH is set in runtime_hook_cuda.py before this import."""

from personalclipboard.app import main

if __name__ == "__main__":
    raise SystemExit(main())
