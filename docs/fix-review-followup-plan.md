# Follow-up Fix Review Plan

## Scope

Address the follow-up findings without changing existing source identities or
claiming runtime behavior that has not been tested in Obsidian. The work is
limited to the URL validation/parser boundary, scanner coverage and structure,
and regression verification.

## Implementation sequence

1. **URL validation before parsing**

   - Add failing tests showing that a raw backslash in a URL input is rejected
     before `strip()` or `urlsplit()` can reinterpret it.
   - Keep percent-encoded backslashes such as `%5C` intact and valid wherever
     the rest of the URL policy permits them; do not decode them as part of
     validation or canonicalization.
   - Add regression cases for ASCII DEL (`U+007F`) and leading/trailing ASCII
     control characters. Preserve the intended treatment of ordinary
     surrounding spaces while rejecting controls deterministically.

2. **Control-character and delimiter tests (TDD)**

   - Write focused tests before changing production code. The raw-backslash
     regression must be run against the old code and observed as a red failure.
     DEL and leading/trailing-control behavior already exists, so those tests
     may be green immediately; use a targeted mutation (temporarily remove the
     relevant validation branch) to prove they fail when the behavior is lost,
     rather than claiming every new test was initially red.
   - Cover DEL, controls around the URL, raw backslash, and `%5C` separately
     so the tests distinguish input rejection from percent-encoded data
     preservation.
   - Implement the smallest validation change that makes the raw-backslash
     test green, then rerun the control tests and their mutation check. Refactor
     only while the focused tests remain green.

3. **Scanner subprocess helper extraction**

   - Extract the scanner subprocess invocation into a small test utility/helper
     rather than constructing a `unittest.TestCase` solely to call an instance
     method.
   - Keep the helper responsible only for launching the scanner, passing the
     repository root, and returning the completed process; assertions remain
     in the tests.
   - Update scanner tests to use the helper directly and preserve their
     existing command-line and output assertions.

4. **Verification and diff review**

   - Run the focused URL/parser and scanner tests first, confirming the
     raw-backslash regression failed before its production change, the
     DEL/control tests detect their targeted mutation, and the final behavior
     passes afterward.
   - Run the complete test suite, the scanner against publishable files,
     Python compilation checks, and `git diff --check`.
   - Inspect the final diff for unintended source-ID/canonicalization changes,
     test-only coupling, generated files, or unrelated edits.
   - Report that no direct Obsidian runtime proof is available in this
     environment; automated parser/audit evidence must not be described as
     equivalent to validation in Obsidian itself.

## Completion criteria

- Raw backslashes are rejected before URL parsing, while `%5C` survives
  unchanged.
- DEL and leading/trailing control-character regressions are covered by
  TDD-first tests.
- Scanner subprocess execution uses an extracted helper and no test creates a
  `TestCase` instance merely to invoke it.
- Full tests, scanner, compile checks, and diff checks pass.
- Final notes explicitly state the absence of Obsidian runtime verification.

## Implementation evidence (2026-09-18)

- Terra Medium ran the raw-backslash regression before the fix: four
  subcases failed as expected. The legacy audit check also reported its
  expected finding (`finding_count: 1`, actual result `0` before the fix).
- The focused post-fix run passed 9 tests. Raw `\\` is rejected before
  stripping/parsing, while `%5C` remains unchanged through both plain and
  angle-destination Markdown round trips.
- DEL-only in-memory mutation removed the `ord(char) == 127` branch and
  produced the intended failure for the trailing-DEL boundary test. The
  leading-DEL case still failed downstream, so the evidence does not claim
  that every control subcase is independently caught by that one mutation.
  A separate control-predicate mutation admitted 11 of 12 cases; this is
  recorded as targeted mutation evidence, not an all-cases claim.
- The scanner subprocess invocation was extracted into `run_scan`; the
  scanner test no longer constructs a `TestCase` merely to call it. The
  legacy audit apply check reported one manual-review finding, zero changed
  files, and unchanged note content.
- Luna High prepared the documentation; the implementation was performed by
  Terra Medium, and the main agent independently verified:
  `python -m unittest discover -s tests -q` (83 tests OK), scanner
  `--root .` (PASS), `compileall -q scripts skills/web-to-obsidian/scripts
  tests` (PASS), and `git diff --check` (PASS).
- No Obsidian runtime check was performed, and no commit was created.
