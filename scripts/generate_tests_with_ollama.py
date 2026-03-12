#!/usr/bin/env python3
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+);", re.MULTILINE)
CLASS_RE = re.compile(r"\bclass\s+(\w+)")
CODE_BLOCK_RE = re.compile(r"```(?:java)?\n(.*?)```", re.DOTALL)


def find_ollama() -> str:
    """Return the full path to ollama or exit with clear install instructions."""
    exe = shutil.which("ollama")
    if exe:
        return exe
    print(
        "ERROR: ollama executable not found on PATH.\n"
        "Install Ollama from https://ollama.com/download\n"
        "Then pull the model:  ollama pull llama3.1\n"
        "And make sure the install directory is on the system PATH.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def run_ollama(prompt, model):
    exe = find_ollama()
    process = subprocess.run(
        [exe, "run", model],
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "ollama run failed")
    return process.stdout


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


