---
name: write-pytest-test
description: How to write a pytest regression test after fixing a bug. Use this once a fix is in place and verified, before considering the task done.
---

# Writing a pytest regression test

After fixing a bug, add a test that fails on the old code and passes on the
fixed code. This proves the bug is gone and stops it from coming back
unnoticed.

## Method

1. **One test, one bug.** Name it after the behavior it protects, not the bug
   report: `test_calculate_discount_applies_percentage`, not
   `test_bug_123`.
2. **Reproduce the exact failing case** you just fixed, with the exact input
   that triggered it — not a different value that happens to also pass.
3. **Assert the precise expected value**, not just "no exception" or
   "not None". A loose assertion can pass even if the fix is wrong.
4. **Keep it independent.** No shared mutable state with other tests, no
   reliance on test execution order.
5. **Put it next to the existing tests** for that module (same test file, or
   a sibling `test_<module>.py`), matching the project's existing naming and
   structure.

## Checklist before considering the fix done

- [ ] The new test fails if you mentally revert the fix.
- [ ] The new test passes with the fix applied.
- [ ] The full test suite still passes (no regression elsewhere).
