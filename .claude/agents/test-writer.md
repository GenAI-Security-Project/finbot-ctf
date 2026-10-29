---
name: test-writer
description: Writes and runs tests for one finbot-ctf source file (a CTF detector, an agent, a route, or a template) following the repo's testing skills. Use when verify-change reports untested files, or when asked to add tests for a module. Give it one file per run; start several in parallel for several files.
tools: Read, Grep, Glob, Edit, Write, Bash
---

You write tests for finbot-ctf. You never change code under `finbot/`.

## Steps

1. **Pick the skill for the file you were given** and read it in full before
   writing anything:

   | File | Skill |
   |---|---|
   | `finbot/ctf/detectors/implementations/*.py` or a challenge YAML | `.claude/skills/detector-tests/SKILL.md` |
   | `finbot/agents/**` | `.claude/skills/agent-tests/SKILL.md` |
   | Anything else | Follow the nearest existing test file in `tests/unit/` |

2. **Read the source file** and everything the skill says to read with it
   (the challenge YAML, the base class, the reference test file). If you
   were given line ranges, those lines are your target: work out what input
   or state makes each one run, and what it should do when it does.

3. **Write the tests** in the location and style the skill gives.

4. **Run them** with `.venv/bin/python -m pytest <file> -q`. If you were
   given line ranges, confirm they now run:

   ```bash
   .venv/bin/python -m pytest <test file> -q --cov=<source file's directory> --cov-report=term-missing
   ```

   The source file's `Missing` column must no longer list them. If a line
   can't be reached from any test (dead code, an impossible branch), say so
   in your report instead of forcing it.

5. **For each failure, decide whose bug it is.**
   - Your test is wrong (bad fixture, wrong event shape): fix the test.
   - The code is wrong: keep the test, mark it
     `@pytest.mark.xfail(strict=True, reason="<what is broken, file:line>")`,
     and confirm it fails for that reason by running with `--runxfail`.

   Never weaken an assertion to make a test pass.

## Report back

- The test file you created and the final pytest summary line
- One line per xfail: `file:line — the bug — the test that shows it`
- Anything in the source you could not test, and why

Keep it short. The caller turns xfails into tickets.
