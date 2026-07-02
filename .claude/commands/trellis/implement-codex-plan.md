<!-- trellis-headless-codex-pack -->
# Implement Codex Plan

Claude Code implements the Codex-approved Trellis plan.

## Preconditions

- The active task status is `in_progress`.
- Headless Codex planning review returned `PASS`.
- `prd.md`, `design.md`, and `implement.md` exist for complex tasks.

## Steps

1. Load context:
   ```bash
   python3 ./.trellis/scripts/get_context.py
   python3 ./.trellis/scripts/get_context.py --mode phase --step 2.1 --platform claude
   ```

2. Read the active task artifacts:
   - `prd.md`
   - `design.md` if present
   - `implement.md` if present
   - `research/` if present
   - relevant `.trellis/spec/**/index.md` files

3. Implement exactly the approved plan.

4. Run focused validation appropriate to the changed scope.

5. Create implementation handoff for Codex:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot implementation-handoff
   ```

Do not commit. Run `/trellis:codex-quality-gate` after implementation.
