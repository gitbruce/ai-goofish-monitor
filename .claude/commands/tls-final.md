<!-- trellis-headless-codex-pack -->
# TLS Final Gate

Short alias for `/trellis:codex-final-gate`.

Use headless Codex to decide whether the active task is ready to commit.

## Steps

1. Create deterministic final-gate request:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot final-gate-request
   ```

2. Run headless Codex final gate:
   ```bash
   FINAL_GATE_REQUEST="$(python3 ./.trellis/scripts/headless_codex_pack.py snapshot-path final-gate-request)"
   (
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-dispatch \
       --run-kind final-gate-request \
       --agent codex-final-gate \
       --request "$FINAL_GATE_REQUEST" \
       --timeout 20m
   )
   ```

3. Interpret the result:
   - `PASS`: prepare a commit plan in Claude Code, ask for confirmation if the
     normal workflow requires it, then commit only the approved files.
   - `MUST-FIX`: fix the listed findings and rerun quality/final gates.
   - `BLOCKED`: stop and report the blocker.

After commit, run `/trellis:finish-work`.
