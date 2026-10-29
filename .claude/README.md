# Claude Code testing library for finbot-ctf

Skills and agents that let Claude Code test finbot-ctf the way this repo
already does by hand: same fixtures, same test IDs, same ticket format.
They cover the path from a requirement, through a feature (written by an
agent or a person), to a merge decision.

```
issue ──► requirements-reviewer ──► acceptance criteria + test map
                                          │
                 feature gets built       ▼
                                    verify-change  (scripts/verify_change.py)
                                          │
              ┌───────────────────────────┼──────────────────────────┐
              ▼                           ▼                          ▼
          BLOCKED                    NEEDS TESTS                  CLEARED
     fix, or qa-ticket        test-writer, one per file    bug-hunter ──► qa-ticket
```

## Skills (`skills/`)

| Skill | Use it to |
|---|---|
| `verify-change` | Gate a branch or PR: affected tests, challenge definition checks, verdict |
| `detector-tests` | Test a CTF detector: success, false positives, gates, config, wiring |
| `agent-tests` | Test an agent with the model mocked: tools, failure modes, context passing |
| `acceptance-criteria` | Turn an issue into testable criteria before code is written |
| `qa-ticket` | Write a bug up in the repo's ticket format |

Run any of them with `/<name>`, or just describe the task. Claude picks the
skill from its description.

## Agents (`agents/`)

| Agent | Does |
|---|---|
| `test-writer` | Writes and runs tests for one file; marks real bugs `xfail(strict=True)` |
| `bug-hunter` | Writes tests meant to break a change; files tickets for what breaks |
| `requirements-reviewer` | Read-only review of an issue for testability |

## The gate script

`scripts/verify_change.py` works without Claude, including in CI:

```bash
python scripts/verify_change.py --base origin/main --run       # affected tests
python scripts/verify_change.py --base origin/main --coverage  # plus changed lines no test runs
```

`--coverage` reports, per changed file, how many changed lines run under
test and which ones don't (for example `67/75; not run: 76, 82-84`).
Below `--min-coverage` (default 80%) the verdict is NEEDS TESTS.

Exit codes: 0 cleared (or not run), 1 blocked, 2 changed source has no
tests or too little of it runs under test.
