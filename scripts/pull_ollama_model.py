#!/usr/bin/env python3
"""Pull an Ollama model using the resolved executable path.

Works on self-hosted Windows runners where `ollama` may not be on PATH
for the runner service account but is installed at a known location.
"""
import argparse
import subprocess
import sys
import urllib.error
import urllib.request
import json
import os

from resolve_ollama import resolve_ollama


def get_ollama_host() -> str:
    return (os.environ.get("OLLAMA_HOST", "").strip() or "http://127.0.0.1:11434").rstrip("/")


def pull_via_cli(exe: str, model: str) -> None:
    print(f"Pulling model '{model}' using: {exe}")
    result = subprocess.run(
        [exe, "pull", model],
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"ollama pull {model} failed with exit code {result.returncode}")
    print(f"Model '{model}' pulled successfully via CLI.")


def pull_via_http(model: str) -> None:
    host = get_ollama_host()
    print(f"Pulling model '{model}' via Ollama HTTP API at {host}")
    url = f"{host}/api/pull"
    payload = json.dumps({"model": model, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Ollama HTTP API unreachable at {host}.\n"
            "Ensure Ollama is running or set OLLAMA_EXE / OLLAMA_HOST."
        ) from exc

    error = body.get("error")
    if error:
        raise SystemExit(f"Ollama pull failed: {error}")
    print(f"Model '{model}' pulled successfully via HTTP API.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull an Ollama model")
    parser.add_argument("--model", required=True, help="Model name to pull (e.g. llama3.1)")
    args = parser.parse_args()

    exe = resolve_ollama()
    if exe:
        pull_via_cli(exe, args.model)
    else:
        pull_via_http(args.model)


if __name__ == "__main__":
    main()

