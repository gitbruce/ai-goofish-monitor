<!-- trellis-headless-codex-pack -->
# TLS Quality Gate

Short alias for `/trellis:codex-quality-gate`.

Use headless Codex to review Claude Code implementation.

## Steps

1. Create deterministic quality-gate request:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot quality-gate-request
   ```

2. Run headless Codex quality gate:
   ```bash
   QUALITY_GATE_REQUEST="$(python3 ./.trellis/scripts/headless_codex_pack.py snapshot-path quality-gate-request)"
   (
     . ./.trellis/scripts/codex_proxy.sh
     python3 ./.trellis/scripts/headless_codex_pack.py codex-dispatch \
       --run-kind quality-gate-request \
       --agent codex-quality-gate \
       --request "$QUALITY_GATE_REQUEST" \
       --timeout 25m
   )
   ```

3. Interpret the result:
   - `PASS`: proceed to `/tls-final` when ready.
   - `MUST-FIX`: fix the listed findings in Claude Code, rerun focused checks,
     then run this command again.
   - `BLOCKED`: stop and report the blocker.

Do not commit from this command.
