# AI Gateway Safety and Quality Rules

## Language

- Think, search, plan, and write code in English.
- User-facing summaries may be written in Arabic.
- Keep code, identifiers, logs, schemas, and technical documentation in English.

## Security

- Never read, print, log, copy, expose, commit, or include API keys or tokens.
- Never place secrets in source files, tests, fixtures, snapshots, reports, artifacts, commands, or generated documentation.
- Read YOUSSEF_BASE_URL and YOUSSEF_API_KEY only from environment variables.
- Never print the value of YOUSSEF_API_KEY.
- Redact Authorization headers and secret-looking values from exceptions and logs.
- Never modify Railway variables, provider keys, Git history, deployment settings, or production infrastructure.
- Never call admin endpoints unless the task explicitly requires them.
- Never weaken authentication, fail-closed behavior, route isolation, or error redaction.
- Never modify backend security behavior unless a failing test proves that a minimal compatibility change is required.
- Never commit generated result files containing live response content without inspecting them for secrets.

## Git Safety

- Work only on the current feature branch.
- Do not push, force-push, merge, rebase, reset --hard, or delete branches.
- Do not modify files unrelated to the requested phase.
- Before finishing, run git status, git diff --check, tests, and secret-oriented checks.
- Do not commit unless explicitly requested by the user.

## Architecture

- Treat every provider_slug::upstream_model_id as an independent route.
- Never merge benchmark results from routes that share the same upstream model name.
- Verify X-Youssef-Resolved-Route for every successful live probe.
- A route mismatch is a failed probe even if the generated response is otherwise correct.
- Keep unit tests offline and deterministic.
- Mark live tests explicitly and never run them as part of the default unit-test suite.
- Store raw run records append-only as JSONL.
- Generate aggregated capability results separately from raw run records.
- Support resuming interrupted probe runs.
- Use bounded concurrency and per-request timeouts.
- Never perform implicit provider or route fallback inside the model lab.

## Engineering Quality

- Use Python 3.12-compatible type hints.
- Keep modules small and single-purpose.
- Use dataclasses or Pydantic models for structured records.
- Use httpx for HTTP requests.
- Validate JSON tool arguments against their schemas.
- Preserve streaming tool-call fragments and assemble them by choice index and tool-call index.
- Include clear failure categories instead of only pass/fail.
- Use pytest and mock transports for unit tests.
- Do not claim completion unless all acceptance criteria are verified with commands and outputs.

## Workflow

- Inspect the repository before changing it.
- Create an implementation plan artifact before editing.
- Identify assumptions and risks.
- Implement in small, testable increments.
- Run focused tests after every major increment.
- Run the complete unit-test suite before finishing.
- Produce a walkthrough artifact with changed files, commands run, results, limitations, and next steps.
