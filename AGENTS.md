# Pi Agent Instructions

## Language

- Communicate with the user in Arabic.
- Write source code, identifiers, technical documentation, and web-search queries in English.

## General Workflow

- Inspect the repository before modifying files.
- Explain the plan before large changes.
- Work only inside the current repository.
- Use subagents for exploration, planning, implementation, testing, and review.
- Run tests after every meaningful implementation.
- Never claim that code works unless the relevant command was actually executed.
- Always inspect git diff before finishing.

## Subagents

For complex programming tasks:

1. Use scout to understand the repository.
2. Use planner to create an implementation plan.
3. Use worker or implementer to execute the approved plan.
4. Use separate reviewers for correctness, tests, security, and unnecessary complexity.
5. Apply only findings supported by concrete evidence.
6. Run a final verifier before reporting completion.
7. Limit review-and-fix loops to three rounds unless the user requests otherwise.

## Safety

- Never read, print, expose, or commit passwords, tokens, API keys, private keys, or credentials.
- Do not read .env, keys.json, keys_no_limit.json, ~/.ssh, ~/.gnupg, browser profiles, or password stores.
- Never use sudo.
- Never execute destructive commands such as rm -rf, git reset --hard, or force push.
- Never modify Railway, production systems, provider credentials, or production databases without explicit user approval.
- Never push, merge, deploy, publish, or create a release without explicit user approval.
- Do not access files outside the current repository unless the user explicitly authorizes a specific path.

## Git

- Work on a feature branch.
- Run git status before starting.
- Use git diff frequently.
- Do not modify unrelated files.
- Run git diff --check before finishing.
- Do not commit unless the user explicitly requests it.

## Web and Browser

- Use Firecrawl for web search and page extraction.
- Use Playwright MCP for browser interaction and web-application testing.
- Never enter secrets into websites without explicit user approval.
- Never upload project files to external services.
- Do not perform purchases, account changes, publishing, or destructive actions.

## Completion Requirements

Before declaring a task complete:

1. Run relevant tests.
2. Run the full offline test suite when practical.
3. Inspect git status.
4. Inspect git diff.
5. Run git diff --check.
6. Run independent correctness, testing, and security reviewers.
7. Report the exact commands executed and their outcomes.
