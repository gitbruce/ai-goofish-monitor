<!-- trellis-headless-codex-pack -->
# TLS Implement

Short alias for `/trellis:implement-codex-plan`.

Claude Code implements the Codex-approved Trellis plan.

## Preconditions

- The active task status is `in_progress`.
- Headless Codex planning review returned `PASS`.
- `prd.md`, `design.md`, and `implement.md` exist for complex tasks.
- Every executable task/slice in `implement.md` has the exact headings `Why`,
  `What`, `How`, `Key Design`, `Dependencies`, `Done When`, and
  `Verification`, including explicit docs-sync instructions.

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

3. Confirm the approved plan is executable without guessing:
   - each task/slice has one clear outcome and ordered steps
   - target files/modules are named where knowable
   - dependencies and rollback points are explicit
   - docs/spec files are named, or the plan states why no docs change is needed
   - verification commands and expected evidence are concrete

   If any of these are missing, stop and ask for plan repair instead of
   inventing implementation details.

4. Implement exactly the approved plan, including docs sync in the same slice
   as the behavior/config/API/schema/UI change it describes.

5. Run the validation commands from `implement.md`. If a command cannot run,
   record the blocker and the evidence collected instead of silently skipping
   it.

6. Create implementation handoff for Codex:
   ```bash
   python3 ./.trellis/scripts/headless_codex_pack.py snapshot implementation-handoff
   ```

Do not commit. Run `/tls-quality` after implementation.
