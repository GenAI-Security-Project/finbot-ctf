# Ticket template

A ticket goes into GitHub in two parts: the **title** in the issue's title
field, and the **body**, starting at `**Component:**`, in the description.
Issues #459 (found by a test) and #444 (found by reading code) are the
reference.

In a `docs/tickets_<area>.md` file, each ticket also gets a `## TICKET <n>`
heading and a `**Title:**` line so the file reads well. Leave both out when
printing a ticket for GitHub.

## File header (new files only)

```markdown
# <Area> QA Tickets
<One line on where these came from: "Generated from intentionally failing tests in
test_<x>.py." or "Findings from a code review of <file>.">
Copy each section as a separate GitHub issue.

---
```

## Title

```
Bug_<NNN>_<MUST_FIX|EVALUATE>: [Test Case ]<AREA>-<TYPE>-<NNN> — <one-line symptom>
```

- `Test Case ` goes in only when a failing test found the bug:
  `Bug_202_EVALUATE: Test Case ORCH-QA-001 — …`. Leave it out for code-review
  findings: `Bug_211_MUST_FIX: AUTH-QA-001 — …`.
- The ID is an area (`ORCH`, `AUTH`, `GRD`) and a type: `QA` for findings,
  or the test category the bug came from (`PROMPT-FUNC-003`).

## Body

````markdown
**Component:** <path/to/file.py> → <Class.method> (line <N>, or lines <N> and <M>)

**Root cause:**

```python
# <file.py> line <N> — <what this part is>
<the lines, copied exactly>
```

<Two or three sentences: why it's wrong and what it causes downstream.>

**Steps to reproduce:**

1. <step>
2. <step>
3. <step>

Expected: <what should happen>
Actual: <what happened, from the real run>

**How to execute:**

```
pytest <path>::<Class>::<test_name> -v --runxfail
```

**Proposed fix:**

```python
# Before (buggy):
<line>

# After (correct):
<line>
```

**Impact:** <Who is affected and how, in two or three sentences. For agent code, what reaches the LLM.>

**Acceptance criteria:**
- `<test_name>` passes (remove its xfail marker)
- <the specific behaviour, stated as a check>
- All other `<area>` tests continue to pass
````

## Which parts are optional

| Part | Include it when |
|---|---|
| `Expected:` / `Actual:` | You ran something. A finding from reading code (#444) lists steps only |
| **How to execute** | A test reproduces the bug. Keep `--runxfail`: confirmed tests are marked `xfail`, and without the flag the command only prints XFAIL |
| Before/After code in **Proposed fix** | The fix is a code change. For a design or consistency problem with several valid fixes, describe the options in prose (#444) |

Aim for the length of #444, about 40 lines. Put detail in the test, not the
ticket.
