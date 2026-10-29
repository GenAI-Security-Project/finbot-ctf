---
name: acceptance-criteria
description: Turn a finbot-ctf GitHub issue, feature idea, or new CTF challenge proposal into testable acceptance criteria and a test plan before any code is written. Flags ambiguous requirements, maps each criterion to a test ID and test layer, and drafts the test-file header. Use when asked to review an issue or spec, write acceptance criteria, plan tests for a feature, or check whether a requirement is testable.
---

# Acceptance criteria

Agents build fast from whatever they're given. A vague issue gets built
vaguely, and the gap shows up as a bug later. This skill moves testing to
the point where the requirement is written.

## Steps

1. **Get the requirement.** For an issue, either:

   ```bash
   gh issue view <n> --repo GenAI-Security-Project/finbot-ctf --comments
   # without gh: the public API needs no login
   curl -s https://api.github.com/repos/GenAI-Security-Project/finbot-ctf/issues/<n>
   curl -s https://api.github.com/repos/GenAI-Security-Project/finbot-ctf/issues/<n>/comments
   ```

   Read linked issues too. If you can't fetch the issue at all, stop and say
   so rather than reconstructing it from other sources.

2. **Find the code it touches.** Name the modules, routes, agents, tools, or
   detectors involved, with paths. Issues go stale: if one names a file that
   doesn't exist, say so and give the path the code lives at now.

3. **Flag what can't be tested yet.**
   - Vague words: "fast", "secure", "handles errors", "works on mobile".
     Propose a measurable version (for example "under 2s at p95", or "44px
     tap targets at 390px width").
   - Missing negative cases: what must *not* happen?
   - For CTF challenges: what counts as success, and what does a normal
     player do with the same tool that must *not* trigger the detector?

4. **Write the criteria.** Each one is a single observable behaviour in
   Given / When / Then form. Number them `<PREFIX>-001`, and so on.

5. **Map each criterion to a test.**

   | ID | Criterion | Layer | File | Skill |
   |---|---|---|---|---|
   | `AUTH-001` | ... | unit / integration / e2e | `tests/...` | `agent-tests` / `detector-tests` |

   Pick the lowest layer that can observe the behaviour. Use e2e only for
   what needs a real browser at phone width.

6. **Draft the test-file header** in the repo's format (User Story /
   Acceptance Criteria / Test Categories; see the top of
   `tests/unit/agents/test_specialized_agents.py`), so whoever builds the
   feature starts from it.

## Output

Print the criteria, the open questions, and the test map in the chat, as
markdown the user can paste into the issue as a comment. Don't post to
GitHub yourself.
