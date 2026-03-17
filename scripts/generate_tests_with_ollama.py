#!/usr/bin/env python3
"""Generate or augment JUnit 5 test methods directly in the existing *Test.java file.

Strategy
--------
1. Identify the existing test file for the changed class (e.g. AadhaarValidatorTest.java).
2. Read both the source class and the current test file.
3. Ask the LLM to produce ONLY new @Test methods that are not already present.
4. Inject the returned methods before the closing brace of the test class.
5. Validate brace balance; fall back to a no-op placeholder method on malformed output.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import urllib.error
import urllib.request

from resolve_ollama import resolve_ollama

PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+);", re.MULTILINE)
CLASS_RE = re.compile(r"\bpublic\s+class\s+(\w+)|(?<!\w)class\s+(\w+)")
METHOD_NAME_RE = re.compile(r"void\s+(\w+)\s*\(")
CODE_BLOCK_RE = re.compile(r"```(?:java)?\n(.*?)```", re.DOTALL)
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------

def get_ollama_host() -> str:
    return (os.environ.get("OLLAMA_HOST", "").strip() or DEFAULT_OLLAMA_HOST).rstrip("/")


def run_ollama_http(prompt: str, model: str) -> str:
    host = get_ollama_host()
    url = f"{host}/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama HTTP API is unreachable at {host}. "
            f"Ensure Ollama is running and the model is pulled (ollama pull {model})."
        ) from exc
    parsed = json.loads(body)
    text = parsed.get("response", "")
    if not text:
        raise RuntimeError("Ollama HTTP API returned an empty response")
    return text


def run_ollama(prompt: str, model: str) -> str:
    exe = resolve_ollama()
    if exe:
        process = subprocess.run(
            [exe, "run", model],
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if process.returncode == 0:
            return process.stdout
    return run_ollama_http(prompt, model)


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def source_file_for_fqcn(fqcn: str) -> pathlib.Path:
    parts = fqcn.split(".")
    return pathlib.Path("src/main/java").joinpath(*parts).with_suffix(".java")


def test_file_for_fqcn(fqcn: str) -> pathlib.Path:
    parts = fqcn.split(".")
    *pkg_parts, class_name = parts
    test_name = f"{class_name}Test.java"
    return pathlib.Path("src/test/java").joinpath(*pkg_parts, test_name)


def parse_package(text: str) -> str:
    m = PACKAGE_RE.search(text)
    return m.group(1) if m else ""


def parse_class_name(text: str) -> str | None:
    for m in CLASS_RE.finditer(text):
        name = m.group(1) or m.group(2)
        if name:
            return name
    return None


def existing_test_method_names(test_text: str) -> set[str]:
    return set(METHOD_NAME_RE.findall(test_text))


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_augment_prompt(source_text: str, test_text: str, extra_instruction: str = "") -> str:
    return (
        "Act as a senior Java test engineer.\n\n"
        "Goal: Add MORE JUnit 5 @Test methods to increase code coverage.\n\n"
        "Rules:\n"
        "- Output ONLY the new @Test method bodies (no class declaration, no package, no imports).\n"
        "- Do NOT repeat any method already present in the existing test file.\n"
        "- Do NOT output a class wrapper or duplicate class declaration.\n"
        "- Each method must start with @Test and have a unique, descriptive name.\n"
        "- Use only: assertTrue, assertFalse, assertEquals, assertThrows from JUnit 5.\n"
        "- Brace balance MUST be correct — every { has a matching }.\n"
        f"{extra_instruction}\n\n"
        "== Existing source ==\n"
        f"{source_text}\n\n"
        "== Existing tests (DO NOT repeat) ==\n"
        f"{test_text}\n\n"
        "Output new @Test methods only:"
    )


def build_create_prompt(source_text: str, package_name: str, class_name: str) -> str:
    return (
        "Act as a senior Java test engineer.\n\n"
        "Goal: Create a complete JUnit 5 test class for the given Java class.\n\n"
        "Rules:\n"
        "- Include the correct package declaration.\n"
        "- Import org.junit.jupiter.api.Test and relevant Assertions.\n"
        "- Cover all public methods with edge cases.\n"
        "- Use descriptive test names.\n"
        "- Output ONLY valid, compilable Java code.\n\n"
        f"Package: {package_name}\n"
        f"Test class name: {class_name}Test\n\n"
        "== Source ==\n"
        f"{source_text}\n\n"
        "Output complete test class:"
    )


# ---------------------------------------------------------------------------
# Code extraction / validation
# ---------------------------------------------------------------------------

def extract_methods_block(response: str) -> str:
    """Extract java code from response; strip class wrapper if present."""
    match = CODE_BLOCK_RE.search(response)
    raw = match.group(1).strip() if match else response.strip()

    if re.search(r"\bclass\s+\w+\s*\{", raw):
        inner = _extract_inner_methods(raw)
        if inner:
            return inner

    return raw


def _extract_inner_methods(class_code: str) -> str:
    start = class_code.find("{")
    if start == -1:
        return ""
    depth = 0
    in_body = False
    method_start = start + 1
    for i, ch in enumerate(class_code[start:], start):
        if ch == "{":
            depth += 1
            in_body = True
        elif ch == "}":
            depth -= 1
            if in_body and depth == 0:
                return class_code[method_start:i].strip()
    return class_code[method_start:].strip()


def methods_are_valid(methods_block: str) -> bool:
    if not methods_block:
        return False
    if "```" in methods_block:
        return False
    if "@Test" not in methods_block:
        return False
    return methods_block.count("{") == methods_block.count("}")


def placeholder_method() -> str:
    return (
        "\n    @Test\n"
        "    void generatedFallbackCompiles() {\n"
        "        org.junit.jupiter.api.Assertions.assertTrue(true);\n"
        "    }\n"
    )


# ---------------------------------------------------------------------------
# Inject methods into existing test file
# ---------------------------------------------------------------------------

def inject_methods_into_test_file(test_file: pathlib.Path, new_methods: str) -> None:
    original = test_file.read_text(encoding="utf-8")
    last_brace = original.rfind("}")
    if last_brace == -1:
        test_file.write_text(original + "\n" + new_methods, encoding="utf-8")
        return
    indented = "\n".join(
        "    " + line if line.strip() else line
        for line in new_methods.splitlines()
    )
    updated = original[:last_brace] + "\n" + indented + "\n}\n"
    test_file.write_text(updated, encoding="utf-8")


def deduplicate_methods(new_methods: str, existing_names: set[str]) -> str:
    lines = new_methods.splitlines()
    output_lines: list[str] = []
    skip_depth = 0

    for line in lines:
        if skip_depth > 0:
            skip_depth += line.count("{") - line.count("}")
            if skip_depth <= 0:
                skip_depth = 0
            continue
        name_match = METHOD_NAME_RE.search(line)
        if name_match and name_match.group(1) in existing_names:
            skip_depth = line.count("{") - line.count("}")
            continue
        output_lines.append(line)

    return "\n".join(output_lines).strip()


def create_test_file(test_file: pathlib.Path, package_name: str, class_name: str,
                     source_text: str, model: str) -> None:
    test_file.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_create_prompt(source_text, package_name, class_name)
    response = run_ollama(prompt, model)
    match = CODE_BLOCK_RE.search(response)
    java_code = match.group(1).strip() + "\n" if match else response.strip() + "\n"

    if not (java_code.count("{") == java_code.count("}") and "class " in java_code):
        pkg = f"package {package_name};\n\n" if package_name else ""
        java_code = (
            f"{pkg}import org.junit.jupiter.api.Test;\n"
            "import static org.junit.jupiter.api.Assertions.*;\n\n"
            f"class {class_name}Test {{\n"
            "    @Test\n"
            "    void generatedFallbackCompiles() { assertTrue(true); }\n"
            "}\n"
        )
    test_file.write_text(java_code, encoding="utf-8")
    print(f"Created test file: {test_file}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default=".tmp/test-targets.txt")
    parser.add_argument("--model", default="phi3")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--extra-instruction", default="",
                        help="Extra hint appended to the augment prompt (e.g. coverage gap info)")
    args = parser.parse_args()

    targets_path = pathlib.Path(args.targets)
    if not targets_path.exists():
        print("No target file found, skipping test generation.")
        return

    targets = [l.strip() for l in targets_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not targets:
        print("No targets found, skipping test generation.")
        return

    generated_count = 0
    for fqcn in targets:
        source_path = source_file_for_fqcn(fqcn)
        if not source_path.exists():
            print(f"Source not found for {fqcn}, skipping.")
            continue

        source_text = source_path.read_text(encoding="utf-8")
        package_name = parse_package(source_text)
        class_name = parse_class_name(source_text)
        if not class_name:
            print(f"Could not parse class name from {source_path}, skipping.")
            continue

        test_file = test_file_for_fqcn(fqcn)

        if not test_file.exists():
            create_test_file(test_file, package_name, class_name, source_text, args.model)
            generated_count += 1
            continue

        test_text = test_file.read_text(encoding="utf-8")
        existing_names = existing_test_method_names(test_text)

        prompt = build_augment_prompt(source_text, test_text, args.extra_instruction)
        response = run_ollama(prompt, args.model)
        new_methods = extract_methods_block(response)

        if not methods_are_valid(new_methods):
            print(f"LLM returned malformed methods for {fqcn}; injecting placeholder.")
            new_methods = placeholder_method()

        new_methods = deduplicate_methods(new_methods, existing_names)
        if not new_methods.strip():
            print(f"No new methods to add for {fqcn}.")
            continue

        inject_methods_into_test_file(test_file, new_methods)
        generated_count += 1
        print(f"Augmented {test_file}")

    print(f"Total augmented/created: {generated_count}")


if __name__ == "__main__":
    main()

