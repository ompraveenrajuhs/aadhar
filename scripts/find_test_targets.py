#!/usr/bin/env python3
import argparse
import pathlib
import re
import subprocess
from collections import defaultdict, deque

CLASS_RE = re.compile(r"\bclass\s+(\w+)")
IMPORT_RE = re.compile(r"^\s*import\s+([\w\.]+);", re.MULTILINE)
PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+);", re.MULTILINE)


def run(cmd):
    return subprocess.check_output(cmd, text=True).strip()


def java_files(root):
    return list(pathlib.Path(root).rglob("*.java"))


def fqcn_of_file(file_path):
    text = file_path.read_text(encoding="utf-8")
    package_match = PACKAGE_RE.search(text)
    class_match = CLASS_RE.search(text)
    if not class_match:
        return None
    class_name = class_match.group(1)
    package = package_match.group(1) if package_match else ""
    return f"{package}.{class_name}" if package else class_name


def imports_of_file(file_path):
    text = file_path.read_text(encoding="utf-8")
    return set(IMPORT_RE.findall(text))


def changed_java_files(base_ref):
    diff = run(["git", "diff", "--name-only", f"{base_ref}...HEAD", "--", "src/main/java"])
    files = [line.strip() for line in diff.splitlines() if line.strip().endswith(".java")]
    return [pathlib.Path(path) for path in files]


def build_dependents_graph(main_root):
    fqcn_to_path = {}
    reverse_deps = defaultdict(set)

    for file_path in java_files(main_root):
        fqcn = fqcn_of_file(file_path)
        if not fqcn:
            continue
        fqcn_to_path[fqcn] = file_path

    for fqcn, file_path in fqcn_to_path.items():
        for imported in imports_of_file(file_path):
            if imported in fqcn_to_path:
                reverse_deps[imported].add(fqcn)

    return fqcn_to_path, reverse_deps


def expand_with_transitive_dependents(initial_fqcns, reverse_deps):
    visited = set(initial_fqcns)
    queue = deque(initial_fqcns)

    while queue:
        current = queue.popleft()
        for dependent in reverse_deps.get(current, set()):
            if dependent not in visited:
                visited.add(dependent)
                queue.append(dependent)

    return visited


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="origin/auto-tests")
    parser.add_argument("--output", default=".tmp/test-targets.txt")
    args = parser.parse_args()

    main_root = pathlib.Path("src/main/java")
    main_root.mkdir(parents=True, exist_ok=True)

    changed = changed_java_files(args.base_ref)
    fqcn_to_path, reverse_deps = build_dependents_graph(main_root)

    changed_fqcns = []
    for path in changed:
        full_path = pathlib.Path(path)
        if full_path.exists():
            fqcn = fqcn_of_file(full_path)
            if fqcn:
                changed_fqcns.append(fqcn)

    all_targets = expand_with_transitive_dependents(changed_fqcns, reverse_deps)

    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sorted(all_targets)), encoding="utf-8")

    print(f"Targets written: {len(all_targets)}")
    for target in sorted(all_targets):
        print(target)


if __name__ == "__main__":
    main()

