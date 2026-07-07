<!-- trellis-headless-codex-pack -->
# TLS Status

Show the current Trellis/Codex pack status without dispatching Codex or
modifying task state. The output distinguishes the shared task state from the
native route and the Codex adapter route.

## Steps

1. Run the deterministic status helper:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py status
   ```

2. Report the helper output directly. If the active task, adapter route, gate
   result, or next step is ambiguous, ask one short routing question using
   ASCII-only labels such as `1.`, `2.`, `3.` or `A.`, `B.`.

This command reports the Codex adapter's view of the shared task artifacts.
Native `/trellis:continue` may choose the upstream Trellis implementation on
the same artifacts.

Do not run `task.py start`, dispatch Codex, edit files, or commit from this
command.
