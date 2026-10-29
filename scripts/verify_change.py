"""
Verify Change

Checks a branch before merge: finds the tests that cover each changed
file, validates any CTF challenge definitions it touches, runs the
affected tests, and prints a verdict. With --coverage it also lists the
changed lines that no test runs.

Built for reviewing AI-written changes, where the usual failure is not
broken code but code that nothing tests.

Audience: Contributors and reviewers — run before opening or merging a PR.

Usage:
    python scripts/verify_change.py                  # list affected tests only
    python scripts/verify_change.py --run            # run unit + integration tests
    python scripts/verify_change.py --coverage       # run them and find changed lines no test runs
    python scripts/verify_change.py --run --e2e      # also run the mobile browser suite
    python scripts/verify_change.py --base origin/main --coverage

Exit codes: 0 cleared (or not run), 1 blocked, 2 changed code has no tests
or too little of it runs under test.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

CHALLENGES_DIR = project_root / "finbot" / "ctf" / "definitions" / "challenges"
TESTS_DIR = project_root / "tests"
E2E_DIR = TESTS_DIR / "e2e"


def git(*args: str) -> list[str]:
    out = subprocess.run(
        ["git", *args], cwd=project_root, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def changed_files(base: str) -> tuple[list[Path], str, set[str]]:
    """Committed, staged, unstaged and untracked changes since `base`.

    Returns the files, the merge base, and the untracked subset.
    """
    merge_base = git("merge-base", base, "HEAD")[0]
    untracked = set(git("ls-files", "--others", "--exclude-standard"))
    names = set(git("diff", "--name-only", merge_base)) | untracked
    files = sorted(project_root / n for n in names if (project_root / n).is_file())
    return files, merge_base, untracked


def changed_lines(path: Path, merge_base: str, untracked: set[str]) -> set[int]:
    """Line numbers in the working copy of `path` that differ from the merge base."""
    rel = str(path.relative_to(project_root))
    if rel in untracked:
        return set(range(1, len(path.read_text().splitlines()) + 1))
    lines: set[int] = set()
    for line in git("diff", "-U0", merge_base, "--", rel):
        hunk = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if hunk:
            start, count = int(hunk[1]), int(hunk[2] or 1)
            lines.update(range(start, start + count))
    return lines


def line_ranges(lines: list[int], executed: set[int]) -> str:
    """Compress line numbers into ranges, bridging gaps that hold no executed code."""
    spans: list[list[int]] = []
    for n in lines:
        if spans and not executed.intersection(range(spans[-1][1] + 1, n)):
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def coverage_of_changes(
    paths: list[Path], merge_base: str, untracked: set[str], report: Path
) -> list[tuple[Path, int, int, str]]:
    """Per file: changed lines run, changed executable lines, ranges not run."""
    measured = json.loads(report.read_text())["files"]
    results = []
    for path in paths:
        data = measured.get(str(path.relative_to(project_root)))
        if not data:
            continue
        executed, missing = set(data["executed_lines"]), set(data["missing_lines"])
        changed = changed_lines(path, merge_base, untracked) & (executed | missing)
        if changed:
            not_run = sorted(changed & missing)
            results.append(
                (path, len(changed) - len(not_run), len(changed), line_ranges(not_run, executed))
            )
    return results


def find_tests(path: Path, test_files: dict[Path, str]) -> list[Path]:
    """Test files that import, patch, or (for detectors) look up this module."""
    dotted = ".".join(path.relative_to(project_root).with_suffix("").parts)
    package, _, leaf = dotted.rpartition(".")
    patterns = [
        rf"\b{re.escape(dotted)}\b",
        rf"from {re.escape(package)} import [^\n]*\b{leaf}\b",
    ]
    # Detectors are created by registered name from YAML, not imported
    for name in re.findall(r'@register_detector\("(\w+)"\)', path.read_text()):
        patterns.append(rf"\b{name}\b")
    return [t for t, text in test_files.items() if any(re.search(p, text) for p in patterns)]


def _challenge_id(path: Path) -> str | None:
    try:
        return (yaml.safe_load(path.read_text()) or {}).get("id")
    except yaml.YAMLError:
        return None


def check_challenges(paths: list[Path]) -> list[str]:
    """Schema, detector wiring and prerequisites for each changed challenge."""
    # pylint: disable=import-outside-toplevel
    from finbot.ctf.detectors.registry import get_detector_class, list_registered_detectors
    from finbot.ctf.schemas.challenge import ChallengeSchema

    known_ids = {_challenge_id(p) for p in CHALLENGES_DIR.rglob("*.yaml")}
    registered = set(list_registered_detectors())
    errors = []
    for path in paths:
        rel = path.relative_to(project_root)
        try:
            challenge = ChallengeSchema(**yaml.safe_load(path.read_text()))
        except Exception as e:  # noqa: BLE001 — report any schema or YAML failure
            errors.append(f"{rel}: invalid definition: {e}")
            continue
        if challenge.detector_class not in registered:
            errors.append(f"{rel}: detector_class {challenge.detector_class} is not registered")
        else:
            try:
                get_detector_class(challenge.detector_class)(
                    challenge_id=challenge.id, config=challenge.detector_config
                )
            except Exception as e:  # noqa: BLE001
                errors.append(f"{rel}: {challenge.detector_class} rejects detector_config: {e}")
        for prereq in sorted(set(challenge.prerequisites) - known_ids):
            errors.append(f"{rel}: prerequisite {prereq} does not exist")
    return errors


def run_pytest(paths: list[Path], coverage_report: Path | None = None) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", *(str(p.relative_to(project_root)) for p in paths)]
    env = dict(os.environ)
    if coverage_report:
        cmd += ["--cov=finbot", f"--cov-report=json:{coverage_report}"]
        env["COVERAGE_FILE"] = str(coverage_report.with_suffix(".data"))
    print(f"\n$ {' '.join(cmd[1:])}", flush=True)
    return subprocess.run(cmd, cwd=project_root, env=env, check=False).returncode == 0


def section(title: str, items: list) -> None:
    print(f"\n{title} ({len(items)}):")
    for item in items:
        print(f"  {item.relative_to(project_root) if isinstance(item, Path) else item}")


@dataclass
class Changes:
    """Changed files sorted by what verifying them needs."""

    affected: set[Path] = field(default_factory=set)  # test files to run
    tested: list[Path] = field(default_factory=list)  # source files some test covers
    untested: list[Path] = field(default_factory=list)  # source files no test touches
    challenges: list[Path] = field(default_factory=list)  # challenge YAML to validate
    ui_changed: bool = False

    def add_test_file(self, path: Path, test_files: dict[Path, str]) -> None:
        if path.name == "conftest.py":
            self.affected.update(t for t in test_files if path.parent in t.parents)
        elif path.name.startswith("test_") and path.suffix == ".py":
            self.affected.add(path)

    def add_source_file(self, path: Path, test_files: dict[Path, str]) -> None:
        if path.suffix == ".py" and path.name != "__init__.py":
            covering = find_tests(path, test_files)
            self.affected.update(covering)
            (self.tested if covering else self.untested).append(path)
        elif path.suffix == ".yaml" and CHALLENGES_DIR in path.parents:
            self.challenges.append(path)
        elif {"templates", "static"} & set(path.relative_to(project_root).parts):
            self.ui_changed = True


def classify(files: list[Path], test_files: dict[Path, str]) -> Changes:
    changes = Changes()
    for path in files:
        top = path.relative_to(project_root).parts[0]
        if top == "tests":
            changes.add_test_file(path, test_files)
        elif top == "finbot":
            changes.add_source_file(path, test_files)
    return changes


def report_coverage(rows: list[tuple[Path, int, int, str]], minimum: float) -> str | None:
    """Print changed-line coverage; return a reason if it is below `minimum`."""
    ran = sum(row[1] for row in rows)
    total = sum(row[2] for row in rows)
    percent = 100 * ran / total
    print(f"\nChanged lines run by tests: {ran}/{total} ({percent:.0f}%, minimum {minimum:.0f}%)")
    for path, file_ran, file_total, not_run in rows:
        gaps = f"not run: {not_run}" if not_run else "all run"
        print(f"  {path.relative_to(project_root)}: {file_ran}/{file_total}; {gaps}")
    return f"only {percent:.0f}% of changed lines run under test" if percent < minimum else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a branch before merge.")
    parser.add_argument("--base", default="main", help="branch to compare against (default: main)")
    parser.add_argument("--run", action="store_true", help="run affected unit and integration tests")
    parser.add_argument("--e2e", action="store_true", help="also run the mobile browser suite")
    parser.add_argument(
        "--coverage", action="store_true",
        help="run affected tests with coverage and list changed lines no test runs (implies --run)",
    )
    parser.add_argument(
        "--min-coverage", type=float, default=80, metavar="PCT",
        help="share of changed lines that must run under test (default: 80)",
    )
    args = parser.parse_args()
    args.run = args.run or args.coverage
    return args


def check_definitions(challenges: list[Path]) -> list[str]:
    """Validate and print the changed challenge definitions."""
    if not challenges:
        return []
    errors = check_challenges(challenges)
    section("Challenge definition problems", errors)
    if not errors:
        print(f"  all {len(challenges)} changed challenge definitions are valid")
    return errors


def verdict(failed: list[str], reasons: list[str], ran: bool) -> int:
    if failed:
        print(f"\n[BLOCKED] {'; '.join(failed)}")
        return 1
    if reasons:
        print(f"\n[NEEDS TESTS] {'; '.join(reasons)}")
        return 2
    if not ran:
        print("\n[NOT RUN] nothing blocking found; rerun with --run for a verdict")
        return 0
    print("\n[CLEARED] affected tests pass and definitions are valid")
    return 0


def main() -> int:
    args = parse_args()
    files, merge_base, untracked = changed_files(args.base)
    changes = classify(files, {p: p.read_text() for p in TESTS_DIR.rglob("test_*.py")})
    browser = sorted(p for p in changes.affected if E2E_DIR in p.parents)
    unit = sorted(changes.affected - set(browser))
    needs_e2e = E2E_DIR.is_dir() and (bool(browser) or changes.ui_changed)

    print(f"Changed files vs {args.base}: {len(files)}")
    section("Affected unit/integration tests", unit)
    section("Changed source files with no tests", changes.untested)
    definition_errors = check_definitions(changes.challenges)
    if needs_e2e:
        print("\nTemplates, CSS or browser tests changed: the mobile suite applies"
              + ("" if args.e2e else " (run with --e2e)"))

    failed = []
    coverage_rows = []
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "coverage.json" if args.coverage else None
        if args.run and unit and not run_pytest(unit, report):
            failed.append("unit/integration tests failed")
        if report and report.exists():
            coverage_rows = coverage_of_changes(changes.tested, merge_base, untracked, report)
    if args.e2e and needs_e2e and not run_pytest([E2E_DIR]):
        failed.append("mobile browser tests failed")
    low_coverage = report_coverage(coverage_rows, args.min_coverage) if coverage_rows else None

    failed += ["challenge definitions invalid"] * bool(definition_errors)
    reasons = [f"{len(changes.untested)} changed source file(s) have no tests"] * bool(changes.untested)
    reasons += [low_coverage] * bool(low_coverage)
    return verdict(failed, reasons, args.run)


if __name__ == "__main__":
    sys.exit(main())
