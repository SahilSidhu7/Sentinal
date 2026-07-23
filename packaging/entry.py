"""PyInstaller entry point for the `sentinal` binary.

A plain module (not `sentinal/__main__.py`) so the frozen build has a single,
unambiguous script to analyze. All it does is hand off to the Typer app.
"""
from sentinal.app import main

if __name__ == "__main__":
    main()
