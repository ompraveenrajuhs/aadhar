#!/usr/bin/env python3
"""Parse JaCoCo XML report and check whether instruction coverage meets the threshold.

Exit codes
----------
0  coverage >= threshold
1  coverage < threshold
2  report not found or unparseable
"""
import argparse
import os
import pathlib
import sys
import xml.etree.ElementTree as ET


DEFAULT_REPORT = "target/site/jacoco/jacoco.xml"
DEFAULT_THRESHOLD = 80


def parse_coverage(report_path: pathlib.Path) -> float:
    """Return overall instruction coverage percentage from jacoco.xml."""
    tree = ET.parse(report_path)
    root = tree.getroot()

    # Top-level <counter type="INSTRUCTION" ...> in the <report> element.
    for counter in root.findall("counter"):
        if counter.get("type") == "INSTRUCTION":
            missed = int(counter.get("missed", "0"))
            covered = int(counter.get("covered", "0"))
            total = missed + covered
            if total == 0:
                return 0.0
            return round(covered / total * 100, 2)

    # Fallback: sum over all packages.
    missed_total = 0
    covered_total = 0
    for counter in root.iter("counter"):
        if counter.get("type") == "INSTRUCTION":
            missed_total += int(counter.get("missed", "0"))
            covered_total += int(counter.get("covered", "0"))

    total = missed_total + covered_total
    if total == 0:
        return 0.0
    return round(covered_total / total * 100, 2)


def write_github_output(key: str, value: str) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check JaCoCo coverage threshold")
    parser.add_argument("--report", default=DEFAULT_REPORT,
                        help="Path to jacoco.xml")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="Minimum required coverage percentage (default 80)")
    args = parser.parse_args()

    report_path = pathlib.Path(args.report)
    if not report_path.exists():
        print(f"Coverage report not found: {report_path}", file=sys.stderr)
        write_github_output("coverage_pct", "0")
        write_github_output("coverage_ok", "false")
        return 2

    try:
        pct = parse_coverage(report_path)
    except Exception as exc:
        print(f"Failed to parse coverage report: {exc}", file=sys.stderr)
        write_github_output("coverage_pct", "0")
        write_github_output("coverage_ok", "false")
        return 2

    ok = pct >= args.threshold
    print(f"Coverage: {pct:.1f}% (threshold: {args.threshold:.0f}%) — {'PASS' if ok else 'FAIL'}")
    write_github_output("coverage_pct", str(pct))
    write_github_output("coverage_ok", "true" if ok else "false")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

