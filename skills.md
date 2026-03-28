# Project Skills

## /commit

Creates a git commit with a well-structured message following this project's conventions.

**Usage:** `/commit`

**What it does:**
1. Runs `git status` and `git diff` to review all staged and unstaged changes
2. Checks recent `git log` to match the existing commit message style
3. Stages relevant files (never `.env`, secrets, or large binaries)
4. Writes a commit message that focuses on *why*, not just *what*
5. Appends `Co-Authored-By: Claude` attribution

**Commit message conventions for this project:**
- Use conventional commits format: `type: short description`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Keep the subject line under 72 characters
- Examples:
  - `feat: add cart mandate escalation for over-threshold trips`
  - `fix: preserve UCP checkout state on payment retry`
  - `refactor: extract segment booking logic into helper`
  - `test: add integration tests for hotel merchant UCP checkout`
  - `chore: update company policy approval threshold to 3000`

**What it will NOT commit:**
- `.env` (contains `ANTHROPIC_API_KEY`)
- `*.pem` key files (VDC signing keys)
- `__pycache__/`, `.pytest_cache/`, `.venv/`
- `travel_agent.db` (local SQLite database)

**Invoke:** Type `/commit` in the Claude Code prompt.
