#!/usr/bin/env python3
"""Ensure Maven is available on PATH for local or CI use.

If `mvn` is not found, this script downloads a Maven binary distribution,
extracts it into the requested install directory, and appends its `bin`
folder to GITHUB_PATH when running inside GitHub Actions.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys
import urllib.request
import zipfile


DEFAULT_VERSION = "3.9.9"


def find_maven() -> str | None:
    return shutil.which("mvn") or shutil.which("mvn.cmd")


def add_to_github_path(path: pathlib.Path) -> None:
    github_path = os.environ.get("GITHUB_PATH")
    if github_path:
        with open(github_path, "a", encoding="utf-8") as handle:
            handle.write(f"{path}\n")


def download_and_extract(version: str, install_dir: pathlib.Path) -> pathlib.Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"apache-maven-{version}-bin.zip"
    archive_path = install_dir / archive_name
    extract_dir = install_dir / f"apache-maven-{version}"

    if not archive_path.exists():
        url = f"https://archive.apache.org/dist/maven/maven-3/{version}/binaries/{archive_name}"
        print(f"Downloading Maven {version} from {url}")
        urllib.request.urlretrieve(url, archive_path)

    if not extract_dir.exists():
        print(f"Extracting Maven into {extract_dir}")
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(install_dir)

    bin_dir = extract_dir / "bin"
    if not bin_dir.exists():
        raise RuntimeError(f"Expected Maven bin directory was not created: {bin_dir}")
    return bin_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure Maven is available")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Maven version to install if missing")
    parser.add_argument(
        "--install-dir",
        default=".tools/maven",
        help="Directory where Maven should be downloaded/extracted when missing",
    )
    args = parser.parse_args()

    existing = find_maven()
    if existing:
        print(f"Maven already available: {existing}")
        existing_path = pathlib.Path(existing).resolve().parent
        add_to_github_path(existing_path)
        return 0

    install_dir = pathlib.Path(args.install_dir).resolve()
    bin_dir = download_and_extract(args.version, install_dir)
    add_to_github_path(bin_dir)
    print(f"Maven installed and ready at: {bin_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

