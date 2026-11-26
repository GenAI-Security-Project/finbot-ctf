---
name: verify-change
description: Verify a finbot-ctf branch or PR before merge, especially one written by an AI agent. Finds the tests that cover each changed file, validates changed CTF challenge definitions, runs the affected tests, fills test gaps, and gives a CLEARED / NEEDS TESTS / BLOCKED verdict. Use when the user asks to verify, check, gate, or review a change, branch, or PR, or asks "is this ready to merge".
---

# Verify change

The gate between "an agent wrote it" and "it ships". The script does the
deterministic work. Your job is to read the result and close the gaps.

## Steps

1. **Run the gate.**

   ```bash
   uv run python scripts/verify_change.py --coverage
   ```

   `--coverage` runs the affected tests and lists, per changed file, the
   changed lines no test runs. Use `--run` instead for a faster pass without
   coverage. Use `--base origin/main` if local `main` is stale. Add `--e2e` when the
   output says templates or CSS changed (needs `playwright install chromium`).
   For a PR that isn't checked out: `gh pr checkout <n>` first.

   If CI already ran, you can start from its report instead:
   `gh run download <run-id> -n verify-change-report` gives
   `verify-change.json`, with each gap's file, line ranges, guide and prompt.
   Still rerun the gate at the end to confirm.

2. **Read the verdict.**

   | Verdict | Meaning | What to do |
   |---|---|---|
   | `[BLOCKED]` | A test failed or a challenge definition is broken | Step 3 |
   | `[NEEDS TESTS]` | Changed files have no tests, or under 80% of changed lines run under test | Step 4 |
   | `[NO TESTS APPLY]` | No changed file is app code or a test (docs, config, templates only) | Say so; nothing to fix |
   | `[CLEARED]` | The tests that import the changed code pass, definitions valid | Step 5 |

3. **Blocked.** For each failure, find the cause in the code (not the test)
   and say which file and line. Common definition failures:
   - `detector_class X is not registered`: the detector module is missing
     from `finbot/ctf/detectors/implementations/__init__.py`.
   - `prerequisite X does not exist`: a typo or a renamed challenge id.
   - `rejects detector_config`: the YAML config doesn't match what the
     detector's `_validate_config` accepts.

   If the user wants the failures filed rather than fixed, use the
   `qa-ticket` skill.

4. **Needs tests.** Delegate to the `test-writer` agent, one agent per
   file, in parallel. There are two kinds of gap:
   - **File with no tests** (listed under "Changed source files with no
     tests"): give the agent the file path.
   - **Lines not run** (listed as `path: 67/75; not run: 76, 82-84`): give
     the agent the file path *and* the line ranges, and say those lines are
     the target. Ignore files that print `all run`.

   Tell each agent to follow the matching skill (`detector-tests` for
   detectors, `agent-tests` for agents). Rerun step 1 when they finish and
   check that the ranges are gone.

5. **Cleared.** Still read the diff once. The gate only proves that tests
   which import the changed code pass. It does not prove those tests check
   the new behaviour. Look for:
   - new branches or config keys that no test exercises
   - detectors with a positive test but no false-positive test
   - agent tool changes with no test of the tool's schema

## Report

End with the verdict, then one line per finding in the form
`file:line — problem — next action`. No finding gets "looks fine" without
a test or a line of code behind it.
