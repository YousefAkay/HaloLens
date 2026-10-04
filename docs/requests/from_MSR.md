# Change requests from MSR

Format: AGENTS.md Section 6.4.

## REQUEST-MSR-01 → INT   status: open
File: requirements.txt
What: add `pydantic>=2,<3` (already installed as a dependency of `anthropic`; scripts/extract_sources.py imports it directly for the structured-output schema)
Why: declare a direct import explicitly instead of relying on a transitive dependency
Blocking: no
Workaround in place: none needed (installed via anthropic)

## REQUEST-MSR-02 → INT   status: open
File: scripts/preflight.py
What: printing `REQUIREMENTS_WARNING` (contains "⚠️") raises UnicodeEncodeError on a Windows cp1252 console, so preflight exits 1 with a traceback. Fix: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at the start of `main()`, or an ASCII-only warning.
Why: `/next` step 0 crashes for Windows teammates whenever requirements.txt changed
Blocking: no (workaround: run with `PYTHONIOENCODING=utf-8`)
Workaround in place: none in code; run `PYTHONIOENCODING=utf-8 .venv\Scripts\python.exe scripts/preflight.py`
