#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse

from resolve_ollama import resolve_ollama

PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+);", re.MULTILINE)
CLASS_RE = re.compile(r"\bclass\s+(\w+)")
CODE_BLOCK_RE = re.compile(r"```(?:java)?\n(.*?)```", re.DOTALL)
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
HEALTH_PATH = "/api/tags"


def get_ollama_host() -> str:
    return (os.environ.get("OLLAMA_HOST", "").strip() or DEFAULT_OLLAMA_HOST).rstrip("/")


def is_local_host(host: str) -> bool:
    parsed = urlparse(host)
    return parsed.hostname in {"127.0.0.1", "localhost", None}


def build_request(path: str, payload: Optional[dict] = None) -> urllib.request.Request:
    url = f"{get_ollama_host()}{path}"
    if payload is None:
        return urllib.request.Request(url, method="GET")
    return urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def is_ollama_healthy(timeout: int = 5) -> bool:
    try:
        req = build_request(HEALTH_PATH)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def start_ollama_server() -> None:
    host = get_ollama_host()
    if not is_local_host(host):
        raise RuntimeError(
            f"Ollama HTTP API is unreachable at {host} and auto-start is only supported for local hosts. "
            "Set OLLAMA_HOST to a reachable server or install/run Ollama locally."
        )

    exe = resolve_ollama()
    if not exe:
        raise RuntimeError(
            "Ollama is not running and no local executable could be found. "
            "Install Ollama or set OLLAMA_EXE to the full path of ollama.exe."
        )

    popen_kwargs = {
        "args": [exe, "serve"],
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(**popen_kwargs)


def ensure_ollama_ready(timeout_seconds: int = 45) -> None:
    if is_ollama_healthy():
        return

    start_ollama_server()
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_ollama_healthy():
            return
        time.sleep(2)

    raise RuntimeError(
        f"Ollama server did not become ready at {get_ollama_host()} within {timeout_seconds} seconds."
    )


def ensure_model_available(model: str) -> None:
    exe = resolve_ollama()
    if exe:
        process = subprocess.run(
            [exe, "pull", model],
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or f"ollama pull {model} failed")
        return

    req = build_request("/api/pull", {"model": model, "stream": False})
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to pull model {model} via Ollama HTTP API") from exc

    parsed = json.loads(body)
    error = parsed.get("error")
    if error:
        raise RuntimeError(f"Ollama pull failed: {error}")


def run_ollama_http(prompt: str, model: str) -> str:
    req = build_request("/api/generate", {"model": model, "prompt": prompt, "stream": False})

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama HTTP API is unreachable at {get_ollama_host()}. "
            "Ensure Ollama is running or set OLLAMA_HOST/OLLAMA_EXE correctly."
        ) from exc

    parsed = json.loads(body)
    text = parsed.get("response", "")
    if not text:
        raise RuntimeError("Ollama HTTP API returned an empty response")
    return text


def run_ollama(prompt, model):
    exe = resolve_ollama()
    if exe:
        process = subprocess.run(
            [exe, "run", model],
            input=prompt,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode == 0:
            return process.stdout

    return run_ollama_http(prompt, model)


def extract_java_code(response):
    match = CODE_BLOCK_RE.search(response)
    if match:
        return match.group(1).strip() + "\n"
    return response.strip() + "\n"


def source_file_for_fqcn(fqcn):
    parts = fqcn.split(".")
    return pathlib.Path("src/main/java").joinpath(*parts).with_suffix(".java")


def target_test_file(package_name, class_name):
    package_path = pathlib.Path("src/test/java").joinpath(*package_name.split(".")) if package_name else pathlib.Path("src/test/java")
    package_path.mkdir(parents=True, exist_ok=True)
    return package_path / f"{class_name}GeneratedTest.java"


def parse_source_metadata(source_text):
    package_match = PACKAGE_RE.search(source_text)
    class_match = CLASS_RE.search(source_text)
    package_name = package_match.group(1) if package_match else ""
    class_name = class_match.group(1) if class_match else None
    return package_name, class_name


def build_prompt(source_text):
    return (
        "Generate a JUnit 5 test class for the following Java source. "
        "Return only valid Java code in one class. "
        "Use clear test names and avoid external dependencies beyond JUnit 5.\n\n"
        f"{source_text}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default=".tmp/test-targets.txt")
    parser.add_argument("--model", default="llama3.1")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    targets_path = pathlib.Path(args.targets)
    if not targets_path.exists():
        print("No target file found, skipping test generation.")
        return

    targets = [line.strip() for line in targets_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not targets:
        print("No targets found, skipping test generation.")
        return

    ensure_ollama_ready()
    ensure_model_available(args.model)

    generated_count = 0
    for fqcn in targets:
        source_path = source_file_for_fqcn(fqcn)
        if not source_path.exists():
            continue

        source_text = source_path.read_text(encoding="utf-8")
        package_name, class_name = parse_source_metadata(source_text)
        if not class_name:
            continue

        target_path = target_test_file(package_name, class_name)
        if target_path.exists() and not args.overwrite:
            continue

        prompt = build_prompt(source_text)
        response = run_ollama(prompt, args.model)
        java_code = extract_java_code(response)
        target_path.write_text(java_code, encoding="utf-8")
        generated_count += 1
        print(f"Generated {target_path}")

    print(f"Total generated tests: {generated_count}")


if __name__ == "__main__":
    main()

