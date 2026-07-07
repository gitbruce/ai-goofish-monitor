<!-- trellis-headless-codex-pack -->
# Headless Codex Brainstorm

Use headless Codex for pre-task project brainstorming from inside Claude Code.

## Preconditions

- The project has run `trellis init -u bruce --claude --codex --gemini`.
- This pack is installed.
- You are in the target project root.

## Dispatch Rule

Immediately dispatch to headless Codex before project exploration. Do not read
project files, list directories, inspect git history, ask clarifying questions,
or brainstorm inline before the `codex-dispatch --agent codex-brainstorm` call.

## Steps

1. Do not answer the brainstorm request yourself. As the first action, create a
   deterministic brainstorm handoff from the user's command arguments and run
   headless Codex brainstormer:
   ```bash
   BRAINSTORM_REQUEST="$(python3 ./.trellis/scripts/headless_codex_pack.py brainstorm-request --prompt "$ARGUMENTS")"
   (
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-dispatch \
      --run-kind brainstorm-request \
      --agent codex-brainstorm \
      --request "$BRAINSTORM_REQUEST" \
      --total-timeout 1h \
      --lease-timeout 5m \
      --stale-timeout 15m
   )
   ```

2. Report the Codex result. Do not create a Trellis task unless the user asks
   to turn one of the options into a task.

Do not implement code in this command.
