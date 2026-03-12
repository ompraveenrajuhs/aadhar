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
import time

from resolve_ollama import resolve_ollama


def get_ollama_host() -> str:
    return (os.environ.get("OLLAMA_HOST", "").strip() or "http://127.0.0.1:11434").rstrip("/")


def pull_via_cli(exe: str, model: str, retries: int, delay_seconds: int) -> None:
    print(f"Pulling model '{model}' using: {exe}")
    last_code = 1
    for attempt in range(1, retries + 1):
        result = subprocess.run(
            [exe, "pull", model],
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"Model '{model}' pulled successfully via CLI.")
            return
        last_code = result.returncode
        if attempt < retries:
            print(f"Pull attempt {attempt}/{retries} failed; retrying in {delay_seconds}s...")
            time.sleep(delay_seconds)

    raise SystemExit(
        f"ollama pull {model} failed after {retries} attempts (last exit code {last_code})."
    )


def pull_via_http(model: str, retries: int, delay_seconds: int) -> None:
    host = get_ollama_host()
    print(f"Pulling model '{model}' via Ollama HTTP API at {host}")
    url = f"{host}/api/pull"
    payload = json.dumps({"model": model, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt < retries:
                print(f"HTTP pull attempt {attempt}/{retries} failed; retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
                continue
            raise SystemExit(
                f"Ollama HTTP API unreachable at {host} after {retries} attempts.\n"
                "Ensure Ollama is running or set OLLAMA_EXE / OLLAMA_HOST."
            ) from exc

        error = body.get("error")
        if error:
            if attempt < retries:
                print(f"HTTP pull attempt {attempt}/{retries} failed with API error; retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
                continue
            raise SystemExit(f"Ollama pull failed after {retries} attempts: {error}")

        print(f"Model '{model}' pulled successfully via HTTP API.")
        return

    raise SystemExit(f"Ollama pull failed after {retries} attempts: {last_error}")


def model_exists_via_cli(exe: str, model: str) -> bool:
    result = subprocess.run([exe, "list"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    names = {line.split()[0] for line in lines[1:] if line.split()}
    return model in names or f"{model}:latest" in names


def model_exists_via_http(model: str) -> bool:
    host = get_ollama_host()
    req = urllib.request.Request(f"{host}/api/tags", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError:
        return False

    names = set()
    for entry in payload.get("models", []):
        for key in ("name", "model"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip())
    return model in names or f"{model}:latest" in names


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull an Ollama model")
    parser.add_argument("--model", required=True, help="Model name to pull (e.g. llama3.1)")
    parser.add_argument("--retries", type=int, default=4, help="Number of pull retry attempts")
    parser.add_argument("--delay-seconds", type=int, default=8, help="Delay between retries in seconds")
    args = parser.parse_args()

    exe = resolve_ollama()
    if exe:
        if model_exists_via_cli(exe, args.model):
            print(f"Model '{args.model}' already exists locally; skipping pull.")
            return
        pull_via_cli(exe, args.model, args.retries, args.delay_seconds)
    else:
        if model_exists_via_http(args.model):
            print(f"Model '{args.model}' already exists on Ollama server; skipping pull.")
            return
        pull_via_http(args.model, args.retries, args.delay_seconds)


if __name__ == "__main__":
    main()

