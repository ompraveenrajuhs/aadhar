#!/usr/bin/env python3
"""Best-effort auto-fix for generated unit tests.

Strategy:
1) Regenerate tests with --overwrite for current target classes.
2) Remove obviously invalid generated test files (empty/too small).
"""

import argparse
import pathlib
import subprocess


def regenerate_tests(targets: str, model: str) -> None:
    cmd = [
        "python",
        "scripts/generate_tests_with_ollama.py",
        "--targets",
        targets,
        "--model",
        model,
        "--overwrite",
    ]
    result = subprocess.run(cmd, text=True, check=False)
    if result.returncode != 0:
        print("Regeneration command failed; proceeding to cleanup fallback.")


def cleanup_invalid_generated_tests() -> int:
    removed = 0
    for test_file in pathlib.Path("src/test/java").rglob("*GeneratedTest.java"):
        try:
            text = test_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # Remove files that are clearly invalid Java outputs from the model.
        if len(text.strip()) < 40 or "class" not in text:
            test_file.unlink(missing_ok=True)
            removed += 1

    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default=".tmp/test-targets.txt")
    parser.add_argument("--model", default="phi3")
    args = parser.parse_args()

    regenerate_tests(args.targets, args.model)
    removed = cleanup_invalid_generated_tests()
    print(f"Auto-fix complete. Removed invalid generated tests: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

