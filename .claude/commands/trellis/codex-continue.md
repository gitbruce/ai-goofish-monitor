<!-- trellis-headless-codex-pack -->
# Headless Codex Continue

Advance the current Trellis task through this pack's Codex-owned workflow
without overriding native `/trellis:continue`.

## Preconditions

- The project has run `trellis init -u bruce --claude --codex --gemini`.
- This pack is installed.
- You are in the target project root.

## Dispatch Rule

Use this command when the user wants the Codex pack flow to decide the next
step. Do not edit `.claude/commands/trellis/continue.md`; the native Trellis
continue command remains outside this pack's ownership.

## Output Format

When asking the user to choose a route, task subset, or go/no-go decision, use
ASCII-only labels such as `1.`, `2.`, `3.` or `A.`, `B.`. Do not use circled
numerals, superscripts, emoji, or other symbolic number glyphs; they can render
too small or mojibake in terminal transcripts.

## Steps

1. Load current context:
   ```bash
   python3 ./.trellis/scripts/get_context.py
   set +e
   PHASE_CONTEXT="$(python3 ./.trellis/scripts/get_context.py --mode phase 2>&1)"
   PHASE_EXIT=$?
   set -e
   printf '%s\n' "$PHASE_CONTEXT"
   if [ "$PHASE_EXIT" -ne 0 ]; then
     echo "get_context.py --mode phase exited $PHASE_EXIT after printing phase context; continue routing from the printed context unless output is empty or malformed." >&2
   fi
   ```

2. Determine the active-task state from `get_context.py` and task artifacts:
   - No active task: classify the request and ask for task-creation consent
     before creating any Trellis task. Use `/tls-brainstorm` only for
     exploratory pre-task brainstorming.
   - `status=planning`: run `/tls-plan`. Do not run `task.py start` until
     headless Codex plan review returns `PASS` and the user has consented to
     implementation.
   - `status=in_progress` and implementation has not started: run `/tls-impl`.
   - `status=in_progress` and implementation or fixes are present: run
     `/tls-quality`.
   - Quality gate `PASS`: run `/tls-final`.
   - Final gate `PASS`: prepare the normal Claude Code commit flow, then run
     `/trellis:finish-work` after the approved commit lands.
   - Any `MUST-FIX`: fix the listed findings in Claude Code, rerun focused
     validation, then rerun `/tls-quality`.
   - Any `BLOCKED`: stop and report the blocker.

3. If the status or previous gate result is ambiguous, load the relevant task
   artifacts and ask one short routing question before acting.

Do not bypass Codex plan review, quality gate, or final gate in this command.
