# Scan prompt (LLM second pass) — moved

The generalized, placeholder-filled version of this prompt now lives at
**docs/alternatives/llm-scan.md**.

It is an *optional* second pass for hard-to-classify emails: run it however
you like, have it write `engine/new_records.json`, and `scripts/run_scan.sh`
(or `python -m engine.cli ingest engine/new_records.json`) merges the file
through the same idempotent path as the built-in Gmail API / IMAP scanners.
