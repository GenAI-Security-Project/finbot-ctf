---
name: qa-ticket
description: Write QA bug tickets for finbot-ctf in the project's standard format (Bug_NNN title, root cause with line numbers, repro steps, pytest command, before/after fix, impact, acceptance criteria). Use when the user asks to write up a bug, file a QA ticket, turn a failing test into an issue, or document findings from a code review.
---

# QA ticket

Turns a failing test or a code-review finding into tickets that can be pasted
straight into GitHub as issues. Tickets are collected per area in
`docs/tickets_<area>.md`.

## Steps

1. **Read the code first.** Open the file at the exact lines the bug lives on.
   Every line number in the ticket must match the current code. Never write a
   ticket from memory or from a test name alone.

2. **Reproduce it.** If a test exposes the bug, run it and record the actual
   output for the Expected/Actual lines:

   ```bash
   pytest <path>::<Class>::<test_name> -v
   ```

   If the finding came from code review and no test exists, say so in the
   file header ("Findings from a code review of `<file>`. These were not
   found by a test.") and give manual repro steps instead of a pytest
   command.

3. **Check for duplicates.** Search the tracker before writing anything:

   ```bash
   gh issue list --repo GenAI-Security-Project/finbot-ctf --state all --search "<keywords>"
   ```

   For a set of two or more tickets, add a "Dedup status" table under the
   file header with one row per finding: existing issue (or "none") and
   whether to file it, comment on an existing issue, or skip it.

4. **Pick the number.** `Bug_NNN` is global across all ticket files. Take the
   highest number in use and add one:

   ```bash
   grep -ho 'Bug_[0-9]*' docs/tickets_*.md 2>/dev/null | sort -t_ -k2 -n | tail -1
   gh issue list --repo GenAI-Security-Project/finbot-ctf --state all --search "Bug_ in:title" --limit 20
   ```

   The first command finds nothing until a ticket file exists; the GitHub
   search is the source of truth.

   The area ID (`ORCH-QA-001`, `AUTH-QA-001`, `MOBILE-QA-001`) counts from 001
   within each file.

5. **Pick the severity.**
   - `MUST_FIX`: security hole, auth bypass, data loss, or users blocked.
   - `EVALUATE`: wrong behaviour that needs a maintainer's judgement call.

6. **Write the ticket** using [ticket-template.md](ticket-template.md).
   Append to `docs/tickets_<area>.md` if it exists. Otherwise create it with
   the file header from the template.

7. **Print every ticket's raw markdown in the chat** so the user can paste
   it into GitHub. Writing the file alone is not enough.

## Rules

- The proposed fix is the smallest change that makes the acceptance test pass.
  Show only the lines that change, as `# Before (buggy):` / `# After (correct):`.
- Impact explains who is hurt and how, in plain words. For agent and LLM code,
  say what bad context or instruction reaches the model.
- Acceptance criteria always include (a) the named test passing and (b) the
  neighbouring tests still passing.
- Do not open issues with `gh issue create`. The user files them.
