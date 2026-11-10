---
name: debug-import-error
description: How to diagnose an ImportError or ModuleNotFoundError methodically before editing any code. Use this when a test or run fails with an import error.
---

# Debugging an ImportError / ModuleNotFoundError

Import errors tempt a quick guess-and-edit loop. Diagnose the exact cause
first — most are one of a small set of causes, and guessing wastes turns.

## Method, in order

1. **Read the exact error message.** It names the missing module or
   attribute. Don't assume; read it character by character
   (`No module named 'foo.bar'` vs `cannot import name 'bar' from 'foo'`
   are different problems).
2. **`cannot import name 'X' from 'Y'`** → `X` doesn't exist in `Y`, or not
   under that name. Read `Y`'s source (or its `__init__.py`) and check the
   real name — a typo, a rename, or a re-export that was removed.
3. **`No module named 'X'`** → `X` itself isn't found.
   - Check the spelling and the package layout (`src/` layout means the
     import path mirrors `src/<package>/...`, not the repo root).
   - Check for a missing `__init__.py` in a package directory.
   - This is a packaging/path issue, not a code logic bug — don't start
     editing unrelated files.
4. **Circular import** (import works alone but fails when triggered from
   another module) → trace which module imports which; the fix is usually
   moving the import or breaking the cycle, not adding more imports.
5. Only after identifying which of the above applies, make the **one**
   targeted fix for it.

## Checklist before editing anything

- [ ] I can state in one sentence which of the 4 cases above this is.
- [ ] I have located the exact line/file where the name is defined (or
  should be).
