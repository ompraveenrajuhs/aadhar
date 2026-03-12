#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess
import sys


def check_branch(remote: str, branch: str) -> int:
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", remote, branch],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        print(f"Branch {branch} does not exist on remote {remote}.", file=sys.stderr)
        return 1
    return 0


def check_targets(targets_file: str) -> int:
    path = pathlib.Path(targets_file)
    has_targets = path.exists() and path.stat().st_size > 0

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as out:
            out.write(f"has_targets={'true' if has_targets else 'false'}\n")

    if has_targets:
        print("Targets found. Proceeding with generation.")
    else:
        print("No Java targets found. Skipping generation and PR update.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    branch_cmd = subparsers.add_parser("check-branch")
    branch_cmd.add_argument("--remote", default="origin")
    branch_cmd.add_argument("--branch", default="auto-tests")

    target_cmd = subparsers.add_parser("check-targets")
    target_cmd.add_argument("--targets", default=".tmp/test-targets.txt")

    args = parser.parse_args()

    if args.command == "check-branch":
        return check_branch(args.remote, args.branch)

    if args.command == "check-targets":
        return check_targets(args.targets)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

