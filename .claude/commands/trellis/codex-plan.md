<!-- trellis-headless-codex-pack -->
# Headless Codex Plan

Use headless Codex to own Trellis Phase 1 planning from inside Claude Code.

## Preconditions

- The project has run `trellis init -u bruce --claude --codex --gemini`.
- This pack is installed.
- You are in the target project root.

## Steps

1. Load current context:
   ```bash
   python3 ./.trellis/scripts/get_context.py
   python3 ./.trellis/scripts/get_context.py --mode phase
   ```

2. If there is no active task, create one only after task-creation consent:
   ```bash
   python3 ./.trellis/scripts/task.py create "<title>" --slug <slug>
   ```

3. Create deterministic planning handoff:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot plan-request
   ```

4. Run headless Codex planner:
   ```bash
   PLAN_REQUEST="$(python3 ./.trellis/scripts/headless_codex_pack.py snapshot-path plan-request)"
   (
     CODEX_USE_PROXY="$(python3 ./.trellis/scripts/headless_codex_pack.py proxy-use --arguments "$ARGUMENTS")"
     export CODEX_USE_PROXY
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-dispatch \
       --run-kind plan-request \
       --agent codex-plan \
       --request "$PLAN_REQUEST" \
       --timeout 30m
   )
   ```

5. Create deterministic review request:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot plan-review-request
   ```

6. Run independent headless Codex planning review:
   ```bash
   PLAN_REVIEW_REQUEST="$(python3 ./.trellis/scripts/headless_codex_pack.py snapshot-path plan-review-request)"
   (
     CODEX_USE_PROXY="$(python3 ./.trellis/scripts/headless_codex_pack.py proxy-use --arguments "$ARGUMENTS")"
     export CODEX_USE_PROXY
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-dispatch \
       --run-kind plan-review-request \
       --agent codex-plan-review \
       --request "$PLAN_REVIEW_REQUEST" \
       --timeout 20m
   )
   ```

7. Interpret the review:
   - `PASS`: run `task.py start` only if the user has already consented to implementation.
   - `MUST-FIX`: run `codex-plan` again with the findings included in the request.
   - `BLOCKED`: stop and report the blocker.

Do not implement code in this command.
