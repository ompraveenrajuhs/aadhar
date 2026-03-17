#!/usr/bin/env python3
import os
import pathlib
import shutil
import sys


def is_executable_file(path: str) -> bool:
    p = pathlib.Path(path)
    return p.exists() and p.is_file()


def resolve_ollama() -> str | None:
    # Allow explicit override from workflow/env (useful for Windows runner services).
    explicit = os.environ.get("OLLAMA_EXE", "").strip()
    if explicit and is_executable_file(explicit):
        return explicit

    which_path = shutil.which("ollama")
    if which_path:
        return which_path

    if os.name == "nt":
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
            os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
        ]
        for candidate in candidates:
            if candidate and is_executable_file(candidate):
                return candidate

    return None


def main() -> int:
    exe = resolve_ollama()
    if not exe:
        print(
            "ERROR: Could not find ollama executable.\n"
            "Set OLLAMA_EXE to the full executable path or add ollama to PATH.\n"
            "Example Windows path: C:\\Users\\<user>\\AppData\\Local\\Programs\\Ollama\\ollama.exe",
            file=sys.stderr,
        )
        return 1

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as out:
            out.write(f"ollama_exe={exe}\n")

    print(f"Resolved ollama executable: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

