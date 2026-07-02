<!-- trellis-headless-codex-pack -->
# TLS Status

Show the current Trellis/Codex pack status without dispatching Codex or
modifying task state.

## Steps

1. Run the deterministic status helper:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py status
   ```

2. Report the helper output directly. If the active task, gate result, or next
   step is ambiguous, ask one short routing question using ASCII-only labels
   such as `1.`, `2.`, `3.` or `A.`, `B.`.

Do not run `task.py start`, dispatch Codex, edit files, or commit from this
command.
