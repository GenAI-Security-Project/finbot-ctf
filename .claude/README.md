# Claude Code testing library for finbot-ctf

Skills and agents that let Claude Code test finbot-ctf the way this repo
already does by hand: same fixtures, same test IDs, same ticket format.
They cover the path from a requirement, through a feature (written by an
agent or a person), to a merge decision.

## Getting started (contributors)

**Tests are written locally; CI only checks them.** CI runs
`scripts/verify_change.py` with no model key, because every test mocks the
model. If it reports `NEEDS TESTS`, the job summary lists the files and line
ranges to cover, the guide for each, and a ready-made prompt.

1. Set up: `uv sync`.
2. Write the missing tests with whatever you have:
   - **Claude Code**, signed in with a Claude subscription (`/login`) or your
     own `ANTHROPIC_API_KEY`: run `claude`, then `/verify-change`.
   - **Another AI assistant** (Codex, Copilot, Cursor, Gemini CLI): paste the
     prompt from the job summary. `AGENTS.md` points it at the same guides.
   - **By hand:** follow the guide for the file.

   You don't need to pay for anything to contribute. Writing tests by hand
   always works, several assistants have free tiers (for example Gemini CLI
   and GitHub Copilot Free), and a local model through Ollama needs no
   account at all. Free tiers have small limits: they suit one prompt per
   gap, not long agent runs. Some use your prompts for training, which is
   fine for this public code, but never paste secrets such as your `.env`
   into any assistant.
3. Check locally until it says `CLEARED`, then push:
   `uv run python scripts/verify_change.py --base origin/main --coverage`

No key is ever stored in this repository or its CI.

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
