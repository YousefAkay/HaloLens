# Change requests from MSR

Format: AGENTS.md Section 6.4.

## REQUEST-MSR-01 → INT   status: open
File: requirements.txt
What: add `pydantic>=2,<3` (already installed as a dependency of `anthropic`; scripts/extract_sources.py imports it directly for the structured-output schema)
Why: declare a direct import explicitly instead of relying on a transitive dependency
Blocking: no
Workaround in place: none needed (installed via anthropic)
