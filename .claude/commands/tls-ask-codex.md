<!-- trellis-headless-codex-pack -->
# TLS Ask Codex

Ask headless Codex to evaluate the current Claude Code work at any time.

This command is not a Trellis task command. It does not create, start, modify,
or finish Trellis tasks, and it does not change native `/trellis:*` command
behavior. It does not create persistent Codex run ledgers or repo artifacts.

## Preconditions

- This pack is installed.
- You are in the target project root.

## Steps

1. Create a temporary request file and ensure it is removed:
   ```bash
   ASK_CODEX_TMPDIR="$(mktemp -d)"
   ASK_CODEX_REQUEST="$ASK_CODEX_TMPDIR/ask-codex-request.md"
   trap 'rm -rf "$ASK_CODEX_TMPDIR"' EXIT
   ```

2. Write a current-context summary into `$ASK_CODEX_REQUEST`. Do this yourself
   from the current conversation and workspace state; do not ask the user to
   write it. If `$ARGUMENTS` is non-empty, treat it as the Codex evaluation
   focus. Include:
   - User request
   - Optional focus from `$ARGUMENTS`
   - What Claude did or plans to do
   - Current conclusion or output to evaluate
   - Files changed or commands run, if any
   - Known uncertainty or blockers
   - Current-scope boundary

   If the current directory is a git repository, include `git status --short`
   and a concise diff summary. Do not paste huge diffs; point Codex to inspect
   the repo read-only when detail is needed.

3. Ask Codex for a scoped gate result:
   ```bash
   (
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-ask \
       --request "$ASK_CODEX_REQUEST" \
       --total-timeout 20m \
       --lease-timeout 5m
   )
   ```

4. Interpret the result:
   - `PASS`: summarize the status and current-scope `Recommendation`.
   - `MUST-FIX`: fix current-scope `P0` and `P1` findings directly, then run
     focused verification and report the fix.
   - `BLOCKED`: stop and report the blocker.

Codex output must stay inside the current scope. Do not act on new features,
broad refactors, migrations, or unrelated cleanup from this command.
