---
name: repo-conventions
description: How to spot and follow a target repository's existing conventions before writing code in it. Use this before editing any file in a repository you haven't worked in yet this session.
---

# Following a repository's own conventions

A fix that works but doesn't match the surrounding code stands out as
obviously AI-written and is harder to review. Match what's already there.

## Method

1. **Read a sibling file before writing one.** Before editing or creating a
   file, read 1-2 other files of the same kind in the same repo (same
   language, same role: another test file, another module) to see the
   actual style in use.
2. **Match, don't introduce:**
   - Naming style (snake_case vs camelCase, prefixes/suffixes already used).
   - Quote style, indentation, import ordering/grouping.
   - Docstring/comment style, or the lack of one.
   - Test framework and assertion style already in use (`assert x == y` vs
     a helper, `pytest` vs `unittest`).
3. **Don't add what the repo doesn't already have.** No new dependency, no
   new abstraction layer, no type-hint style the rest of the codebase
   doesn't use, just to fix one bug.
4. **When in doubt, prefer the smallest diff** that fits the existing
   pattern over a "better" pattern that isn't there yet.

## Checklist before editing

- [ ] I've read at least one existing file of the same kind in this repo.
- [ ] My change uses the same naming and structure as that file.
