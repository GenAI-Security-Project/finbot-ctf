# Ticket template

## File header (new files only)

```markdown
# <Area> QA Tickets
<One line on where these came from: "Generated from intentionally failing tests in
test_<x>.py." or "Findings from a code review of <file>.">
Copy each section as a separate GitHub issue.

---
```

## One ticket

````markdown
## TICKET <n>

**Title:** Bug_<NNN>_<MUST_FIX|EVALUATE>: <AREA>-QA-<NNN> — <one-line symptom>

**Component:** <path/to/file.py> → <Class.method> (line <N>)

**Root cause:**

```python
# <file.py> line <N>
<the buggy lines, copied exactly>
```

<Two or three sentences: why this code is wrong and what it causes downstream.>

**Steps to reproduce:**

1. <step>
2. <step>
3. <step>

Expected: <what should happen>
Actual: <what happens, from the real test run>

**How to execute:**

```
pytest <path>::<Class>::<test_name> -v
```

**Proposed fix:**

```python
# Before (buggy):
<line>

# After (correct):
<line>
```

**Impact:** <Who is affected and how. For agent code, what reaches the LLM.>

**Acceptance criteria:**
- `<test_name>` passes
- <the specific behaviour, stated as a check>
- All other `<method>` tests continue to pass

---
````
