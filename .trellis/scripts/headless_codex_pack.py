#!/usr/bin/env python3
"""Deterministic helpers for the headless Codex Trellis pack.

The helper creates handoff snapshots from local files. It does not decide which
tests matter or whether a plan is good; Codex agents do that.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACK_MARKER = "trellis-headless-codex-pack"

EXPECTED_SNIPPETS = {
    ".claude/commands/trellis/codex-brainstorm.md": [
        PACK_MARKER,
        "codex-brainstorm",
        "codex-dispatch",
        "--run-kind brainstorm-request",
        "--agent codex-brainstorm",
        "Do not read\nproject files",
    ],
    ".claude/commands/trellis/codex-plan.md": [
        PACK_MARKER,
        "codex-dispatch",
        "--run-kind plan-request",
        "--agent codex-plan",
        "--run-kind plan-review-request",
        "--agent codex-plan-review",
    ],
    ".claude/commands/trellis/codex-continue.md": [
        PACK_MARKER,
        "without overriding native `/trellis:continue`",
        "ASCII-only labels",
        "Do not use circled\nnumerals",
        "PHASE_EXIT=$?",
        "continue routing from the printed context unless output is empty or malformed",
        "`status=planning`: run `/tls-plan`",
        "Do not bypass Codex plan review",
    ],
    ".claude/commands/trellis/implement-codex-plan.md": [
        PACK_MARKER,
        "implementation-handoff",
        "/trellis:codex-quality-gate",
    ],
    ".claude/commands/trellis/codex-quality-gate.md": [
        PACK_MARKER,
        "codex-dispatch",
        "--run-kind quality-gate-request",
        "--agent codex-quality-gate",
    ],
    ".claude/commands/trellis/codex-final-gate.md": [
        PACK_MARKER,
        "codex-dispatch",
        "--run-kind final-gate-request",
        "--agent codex-final-gate",
    ],
    ".claude/commands/tls-brainstorm.md": [
        PACK_MARKER,
        "/trellis:codex-brainstorm",
        "codex-dispatch",
        "--run-kind brainstorm-request",
        "--agent codex-brainstorm",
    ],
    ".claude/commands/tls-plan.md": [
        PACK_MARKER,
        "/trellis:codex-plan",
        "codex-dispatch",
        "--run-kind plan-request",
        "--agent codex-plan",
        "--run-kind plan-review-request",
        "--agent codex-plan-review",
    ],
    ".claude/commands/tls-continue.md": [
        PACK_MARKER,
        "/trellis:codex-continue",
        "ASCII-only labels",
        "Do not use circled\nnumerals",
        "PHASE_EXIT=$?",
        "continue routing from the printed context unless output is empty or malformed",
        "`status=planning`: run `/tls-plan`",
        "Do not bypass Codex plan review",
    ],
    ".claude/commands/tls-status.md": [
        PACK_MARKER,
        "headless_codex_pack.py status",
        "Do not run `task.py start`, dispatch Codex, edit files, or commit",
    ],
    ".claude/commands/tls-impl.md": [
        PACK_MARKER,
        "/trellis:implement-codex-plan",
        "implementation-handoff",
        "/tls-quality",
    ],
    ".claude/commands/tls-quality.md": [
        PACK_MARKER,
        "/trellis:codex-quality-gate",
        "codex-dispatch",
        "--run-kind quality-gate-request",
        "--agent codex-quality-gate",
    ],
    ".claude/commands/tls-final.md": [
        PACK_MARKER,
        "/trellis:codex-final-gate",
        "codex-dispatch",
        "--run-kind final-gate-request",
        "--agent codex-final-gate",
    ],
    ".trellis/agents/codex-brainstorm.md": [
        PACK_MARKER,
        "name: codex-brainstorm",
        "provider: codex",
    ],
    ".trellis/agents/codex-plan.md": [
        PACK_MARKER,
        "name: codex-plan",
        "provider: codex",
    ],
    ".trellis/agents/codex-plan-review.md": [
        PACK_MARKER,
        "name: codex-plan-review",
        "provider: codex",
    ],
    ".trellis/agents/codex-quality-gate.md": [
        PACK_MARKER,
        "name: codex-quality-gate",
        "provider: codex",
    ],
    ".trellis/agents/codex-final-gate.md": [
        PACK_MARKER,
        "name: codex-final-gate",
        "provider: codex",
    ],
    ".trellis/scripts/headless_codex_pack.py": [
        PACK_MARKER,
        "task_status_report",
        "verify-install",
        "brainstorm-request",
        "codex-dispatch",
        "codex-status",
        "codex-resume",
    ],
    ".trellis/scripts/codex_proxy.sh": [
        PACK_MARKER,
        "http_proxy",
        "https_proxy",
    ],
}

WORKFLOW_SNIPPETS = [
    PACK_MARKER,
    "/tls-brainstorm",
    "/tls-continue",
    "/tls-status",
    "/tls-plan",
    "/tls-impl",
    "/tls-quality",
    "/tls-final",
    "/trellis:codex-brainstorm",
    "/trellis:codex-continue",
    "/trellis:codex-plan",
    "/trellis:codex-quality-gate",
    "/trellis:codex-final-gate",
    "ASCII-only labels",
    "[workflow-state:planning]",
    "[workflow-state:in_progress]",
]

WORKFLOW_STATE_SNIPPETS = {
    "planning": (
        f"{PACK_MARKER}: for Codex-owned flow use `/tls-continue` or "
        "`/trellis:codex-continue`; `task.py start` is blocked "
        "until headless Codex plan review says PASS."
    ),
    "in_progress": (
        f"{PACK_MARKER}: for Codex-owned flow use `/tls-continue` or "
        "`/trellis:codex-continue`; Claude implements, then headless Codex "
        "quality/final gates run before commit."
    ),
}

TERMINAL_EVENT_KINDS = {"done", "killed", "error"}
TASK_RUN_KINDS = {
    "plan-request",
    "plan-review-request",
    "quality-gate-request",
    "final-gate-request",
    "implementation-handoff",
}
PACK_RUN_KINDS = {"brainstorm-request"}
ALL_RUN_KINDS = sorted(TASK_RUN_KINDS | PACK_RUN_KINDS)

COMMAND_CLASSES = {
    "codex_dispatch_commands": [
        ".claude/commands/trellis/codex-brainstorm.md",
        ".claude/commands/trellis/codex-plan.md",
        ".claude/commands/trellis/codex-quality-gate.md",
        ".claude/commands/trellis/codex-final-gate.md",
        ".claude/commands/tls-brainstorm.md",
        ".claude/commands/tls-plan.md",
        ".claude/commands/tls-quality.md",
        ".claude/commands/tls-final.md",
    ],
    "router_commands": [
        ".claude/commands/trellis/codex-continue.md",
        ".claude/commands/tls-continue.md",
    ],
    "local_status_commands": [
        ".claude/commands/tls-status.md",
    ],
    "claude_owned_commands": [
        ".claude/commands/trellis/implement-codex-plan.md",
        ".claude/commands/tls-impl.md",
    ],
    "native_unmanaged_commands": [
        ".claude/commands/trellis/continue.md",
        ".claude/commands/trellis-brainstorm.md",
    ],
}

CHANNEL_HELP_REQUIREMENTS = {
    "create": ["--scope", "--cwd", "--description", "--context-file"],
    "spawn": ["--scope", "--agent", "--provider", "--as", "--cwd", "--resume", "--timeout"],
    "send": ["--scope", "--as", "--to", "--text-file", "--delivery-mode"],
    "wait": ["--scope", "--as", "--to", "--kind", "--include-progress", "--timeout", "--from"],
    "messages": ["--scope", "--raw", "--since", "--last", "--follow"],
}


def run(args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(args, text=True, capture_output=True)
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def current_task() -> Path:
    code, out, err = run(["python3", "./.trellis/scripts/task.py", "current", "--source"])
    if code != 0:
        raise SystemExit(err or out or "No active task.")
    for line in out.splitlines():
        if line.startswith("Current task:"):
            value = line.split(":", 1)[1].strip()
            if value and value != "(none)":
                return Path(value)
    raise SystemExit("No active task. Create a Trellis task first.")


def rel(path: Path) -> str:
    try:
        return path.relative_to(Path(".")).as_posix()
    except ValueError:
        return path.as_posix()


def artifact_status(task: Path) -> str:
    names = ["task.json", "prd.md", "design.md", "implement.md", "implement.jsonl", "check.jsonl"]
    lines = []
    for name in names:
        p = task / name
        if p.exists():
            lines.append(f"- {rel(p)}: present")
        else:
            lines.append(f"- {rel(p)}: missing")
    return "\n".join(lines)


def docs_candidates() -> str:
    candidates: list[str] = []
    for name in ["AGENTS.md", "CLAUDE.md", "README.md"]:
        if Path(name).exists():
            candidates.append(name)
    for base in ["docs/requirement", "docs/requirements", "docs"]:
        root = Path(base)
        if root.is_dir():
            for p in sorted(root.rglob("*.md"))[:80]:
                candidates.append(p.as_posix())
    if not candidates:
        return "- (none found by deterministic scan)"
    return "\n".join(f"- {p}" for p in candidates)


def project_entrypoints() -> str:
    names = [
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
        "package.json",
        "pnpm-workspace.yaml",
        "pyproject.toml",
        "requirements.txt",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
    ]
    found = [name for name in names if Path(name).exists()]
    if not found:
        return "- (none found by deterministic scan)"
    return "\n".join(f"- {p}" for p in found)


def packages_context() -> str:
    code, out, err = run(["python3", "./.trellis/scripts/get_context.py", "--mode", "packages"])
    if code != 0:
        return err or out or "(package context unavailable)"
    return out


def git_snapshot() -> str:
    _, status, _ = run(["git", "status", "--short"])
    _, names, _ = run(["git", "diff", "--name-only", "HEAD"])
    return "\n".join(
        [
            "### git status --short",
            status or "(clean)",
            "",
            "### git diff --name-only HEAD",
            names or "(no diff)",
        ]
    )


def current_task_or_none() -> tuple[Path | None, str | None]:
    code, out, err = run(["python3", "./.trellis/scripts/task.py", "current", "--source"])
    if code != 0:
        return None, err or out or "task.py current failed"
    for line in out.splitlines():
        if line.startswith("Current task:"):
            value = line.split(":", 1)[1].strip()
            if value and value != "(none)":
                return Path(value), None
            return None, None
    return None, "task.py current output did not include an active task"


def read_json_object(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing: {rel(path)}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON: {rel(path)} ({exc})"
    if not isinstance(data, dict):
        return {}, f"invalid JSON object: {rel(path)}"
    return data, None


def jsonl_real_entry_count(path: Path) -> tuple[int, str | None]:
    if not path.exists():
        return 0, "missing"
    count = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return 0, str(exc)
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError:
            return count, "invalid JSONL"
        if not isinstance(item, dict):
            continue
        file_value = item.get("file")
        if isinstance(file_value, str) and file_value.strip() and file_value.strip() != "_example":
            count += 1
    return count, None


def latest_run_records(task: Path) -> list[tuple[Path, dict[str, Any]]]:
    root = task / "handoff" / "codex-runs"
    if not root.is_dir():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for run_json in sorted(root.glob("*/run.json")):
        data, error = read_json_object(run_json)
        if error:
            continue
        records.append((run_json.parent, data))
    records.sort(key=lambda item: str(item[1].get("updated_at") or item[1].get("created_at") or ""), reverse=True)
    return records


def outcome_from_messages(path: Path) -> str:
    if not path.exists():
        return "unknown"
    text = path.read_text(encoding="utf-8", errors="replace")
    for token in ["MUST-FIX", "BLOCKED", "PASS"]:
        if token in text:
            return token
    return "unknown"


def latest_outcome(task: Path, run_kind: str) -> tuple[str, str]:
    for directory, data in latest_run_records(task):
        if data.get("run_kind") != run_kind:
            continue
        messages = directory / "messages.jsonl"
        outcome = outcome_from_messages(messages)
        status = str(data.get("status") or "unknown")
        return outcome, f"{rel(directory)} ({status})"
    return "missing", "(none)"


def task_status_report() -> int:
    print("Trellis Headless Codex Pack Status")
    print()

    task, task_error = current_task_or_none()
    if task is None:
        print("Active task:")
        print("- path: (none)")
        if task_error:
            print(f"- detail: {task_error}")
        print()
        print("Next:")
        print("- slash command: /tls-brainstorm <topic> for exploration, or /tls-plan after task-creation consent")
        print("- note: /tls-status is read-only and does not create or start tasks")
        print()
        print("Git snapshot:")
        print(git_snapshot())
        return 0

    task_data, task_json_error = read_json_object(task / "task.json")
    status = str(task_data.get("status") or "unknown") if not task_json_error else "unknown"
    title = task_data.get("title") or task_data.get("name") or task_data.get("slug") or task.name

    print("Active task:")
    print(f"- path: {rel(task)}")
    print(f"- title: {title}")
    print(f"- task status: {status}")
    if task_json_error:
        print(f"- task.json: {task_json_error}")

    print()
    print("Artifacts:")
    for name in ["prd.md", "design.md", "implement.md"]:
        state = "present" if (task / name).exists() else "missing"
        print(f"- {name}: {state}")
    for name in ["implement.jsonl", "check.jsonl"]:
        count, error = jsonl_real_entry_count(task / name)
        detail = f"{count} real entries"
        if error:
            detail += f"; {error}"
        print(f"- {name}: {detail}")

    print()
    print("Codex gates:")
    plan_outcome, plan_source = latest_outcome(task, "plan-review-request")
    quality_outcome, quality_source = latest_outcome(task, "quality-gate-request")
    final_outcome, final_source = latest_outcome(task, "final-gate-request")
    print(f"- plan review: {plan_outcome}; source: {plan_source}")
    print(f"- quality gate: {quality_outcome}; source: {quality_source}")
    print(f"- final gate: {final_outcome}; source: {final_source}")

    handoff = task / "handoff" / "implementation-handoff.md"
    implementation_handoff = handoff.exists()
    next_items: list[str] = []

    if status == "planning":
        if plan_outcome == "PASS":
            next_items = [
                "shell action: python3 ./.trellis/scripts/task.py start <task-dir>",
                "slash command after start: /tls-impl",
                "why no immediate slash command: activation is a task.py state transition, not a slash-command phase",
                "fallback slash command: /tls-continue",
            ]
        elif plan_outcome == "BLOCKED":
            next_items = [
                "slash command: /tls-plan after resolving the blocker",
            ]
        else:
            next_items = [
                "slash command: /tls-plan",
            ]
    elif status == "in_progress":
        if not implementation_handoff:
            next_items = [
                "slash command: /tls-impl",
            ]
        elif quality_outcome != "PASS":
            next_items = [
                "slash command: /tls-quality",
            ]
        elif final_outcome != "PASS":
            next_items = [
                "slash command: /tls-final",
            ]
        else:
            next_items = [
                "shell action: commit approved files",
                "slash command after commit: /trellis:finish-work",
                "why no immediate slash command: commit is a git operation, not a slash-command phase",
                "fallback slash command: /tls-continue",
            ]
    elif status == "completed":
        next_items = [
            "slash command: /trellis:finish-work if the task is not archived yet",
        ]
    else:
        next_items = [
            "slash command: /tls-plan if still planning, or /tls-impl if already started",
        ]

    print()
    print("Next:")
    for item in next_items:
        print(f"- {item}")

    recent = latest_run_records(task)[:3]
    print()
    print("Recent Codex runs:")
    if not recent:
        print("- (none)")
    for directory, data in recent:
        print(
            f"- {data.get('run_kind', 'unknown')}: {data.get('status', 'unknown')}; "
            f"agent={data.get('agent', 'unknown')}; run={directory.name}"
        )

    print()
    print("Git snapshot:")
    print(git_snapshot())
    return 0


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def snapshot(kind: str, output: Path | None) -> str:
    task = current_task()
    handoff = task / "handoff"
    handoff.mkdir(parents=True, exist_ok=True)

    text = f"""# {kind.replace('-', ' ').title()} Handoff

Generated by `{PACK_MARKER}`.

## Active Task

{rel(task)}

## Task Artifacts

{artifact_status(task)}

## Package / Spec Index

```text
{packages_context()}
```

## Candidate Project Docs

{docs_candidates()}

## Git Snapshot

```text
{git_snapshot()}
```

## Instructions For Reviewer

Use the files above as entry points. Choose relevant specs, requirement docs,
and verification commands from the target project. Return only PASS, MUST-FIX,
or BLOCKED with concrete file:line findings.
"""
    if output is None:
        output = handoff / f"{kind}.md"
    write(output, text)
    return rel(output)


def brainstorm_request(prompt: str, output: Path | None) -> str:
    text = f"""# Brainstorm Request Handoff

Generated by `{PACK_MARKER}`.

## User Request

{prompt.strip() or "(no explicit brainstorm prompt provided)"}

## Project Entry Points

{project_entrypoints()}

## Package / Spec Index

```text
{packages_context()}
```

## Candidate Project Docs

{docs_candidates()}

## Git Snapshot

```text
{git_snapshot()}
```

## Instructions For Codex Brainstormer

Use the target project cwd as the source of truth. Inspect files as needed.
Brainstorm only: do not edit files, create a Trellis task, start a task, or
write planning artifacts. Return concrete enhancement options and the best next
task candidate if one is clear.
"""
    if output is None:
        output = Path(".trellis") / "headless-codex-pack" / "brainstorm-request.md"
    write(output, text)
    return rel(output)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return token or "run"


def run_root(run_kind: str) -> Path:
    if run_kind in PACK_RUN_KINDS:
        return Path(".trellis") / "headless-codex-pack" / "codex-runs"
    if run_kind in TASK_RUN_KINDS:
        return current_task() / "handoff" / "codex-runs"
    raise SystemExit(f"Unsupported Codex run kind: {run_kind}")


def run_dir_for(run_kind: str, run_id: str) -> Path:
    return run_root(run_kind) / run_id


def find_run_dir(run_id: str) -> Path:
    candidates: list[Path] = []
    pack_dir = Path(".trellis") / "headless-codex-pack" / "codex-runs" / run_id
    if pack_dir.exists():
        candidates.append(pack_dir)
    try:
        task_dir = current_task() / "handoff" / "codex-runs" / run_id
    except SystemExit:
        task_dir = Path("__missing__")
    if task_dir.exists():
        candidates.append(task_dir)

    tasks_root = Path(".trellis") / "tasks"
    if tasks_root.is_dir():
        for task_root in sorted(tasks_root.iterdir()):
            candidate = task_root / "handoff" / "codex-runs" / run_id
            if candidate.exists() and candidate not in candidates:
                candidates.append(candidate)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        paths = ", ".join(rel(path) for path in candidates)
        raise SystemExit(f"Ambiguous Codex run {run_id}: {paths}")
    raise SystemExit(f"Codex run not found: {run_id}")


def save_json(path: Path, data: dict[str, Any]) -> None:
    write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON file: {rel(path)}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid JSON object file: {rel(path)}")
    return data


def make_run(run_kind: str, agent: str, request_path: Path, timeout: str) -> tuple[Path, dict[str, Any]]:
    root = run_root(run_kind)
    base_run_id = f"{utc_stamp()}-{safe_token(agent)}"
    for index in range(1000):
        run_id = base_run_id if index == 0 else f"{base_run_id}-{index + 1}"
        directory = root / run_id
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        break
    else:
        raise SystemExit(f"Unable to allocate Codex run directory for: {base_run_id}")

    channel = f"hcx-{run_id}"
    messages_path = directory / "messages.jsonl"
    now = utc_now()
    request_rel = rel(request_path)
    run_data = {
        "run_id": run_id,
        "run_kind": run_kind,
        "agent": agent,
        "channel": channel,
        "scope": "project",
        "request_path": request_rel,
        "timeout": timeout,
        "status": "created",
        "last_seq": 0,
        "provider_resume_id": None,
        "created_at": now,
        "updated_at": now,
        "messages_path": rel(messages_path),
    }
    save_json(directory / "run.json", run_data)
    return directory, run_data


def run_required(args: list[str]) -> str:
    code, out, err = run(args)
    if code != 0:
        command = " ".join(args)
        detail = err or out or f"exit {code}"
        raise SystemExit(f"Command failed: {command}\n{detail}")
    return out


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def event_seq(event: dict[str, Any]) -> int:
    value = event.get("seq", 0)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def event_kind(event: dict[str, Any]) -> str:
    value = event.get("kind", "")
    return value if isinstance(value, str) else ""


def extract_resume_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("provider_resume_id", "resume_id", "codex_session_id"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
        for item in value.values():
            found = extract_resume_id(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = extract_resume_id(item)
            if found:
                return found
    return None


def sync_messages(directory: Path, run_data: dict[str, Any]) -> list[dict[str, Any]]:
    messages_path = directory / "messages.jsonl"
    seen_seqs: set[int] = set()
    if messages_path.exists():
        for raw_line in messages_path.read_text(encoding="utf-8").splitlines():
            try:
                existing = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if isinstance(existing, dict):
                seq = event_seq(existing)
                if seq:
                    seen_seqs.add(seq)

    since = max(int(run_data.get("last_seq") or 0), max(seen_seqs, default=0))
    run_data["last_seq"] = since
    out = run_required(
        [
            "trellis",
            "channel",
            "messages",
            str(run_data["channel"]),
            "--scope",
            str(run_data["scope"]),
            "--raw",
            "--since",
            str(since),
        ]
    )
    events: list[dict[str, Any]] = []
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"kind": "text", "message": line}
        if not isinstance(event, dict):
            event = {"kind": "text", "message": line}
        seq = event_seq(event)
        run_data["last_seq"] = max(int(run_data.get("last_seq") or 0), seq)
        if seq and seq in seen_seqs:
            continue
        if seq:
            seen_seqs.add(seq)
        events.append(event)
        append_text(messages_path, json.dumps(event, sort_keys=True) + "\n")
        resume_id = extract_resume_id(event)
        if resume_id:
            run_data["provider_resume_id"] = resume_id
    run_data["updated_at"] = utc_now()
    save_json(directory / "run.json", run_data)
    return events


def terminal_status(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        kind = event_kind(event)
        if kind == "done":
            return "done"
        if kind == "killed":
            return "killed"
        if kind == "error":
            return "failed"
    return None


def update_run(directory: Path, run_data: dict[str, Any], status: str | None = None) -> None:
    if status is not None:
        run_data["status"] = status
    run_data["updated_at"] = utc_now()
    save_json(directory / "run.json", run_data)


def create_channel(directory: Path, run_data: dict[str, Any], request_path: Path) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "create",
            str(run_data["channel"]),
            "--scope",
            str(run_data["scope"]),
            "--cwd",
            str(Path(".").resolve()),
            "--description",
            f"{PACK_MARKER} {run_data['run_kind']} {run_data['agent']}",
            "--context-file",
            str(request_path.resolve()),
        ]
    )
    update_run(directory, run_data, "channel-created")


def spawn_worker(directory: Path, run_data: dict[str, Any]) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "spawn",
            str(run_data["channel"]),
            "--scope",
            str(run_data["scope"]),
            "--agent",
            str(run_data["agent"]),
            "--provider",
            "codex",
            "--as",
            str(run_data["agent"]),
            "--cwd",
            str(Path(".").resolve()),
            "--timeout",
            str(run_data["timeout"]),
        ]
    )
    update_run(directory, run_data, "worker-spawned")


def send_request(directory: Path, run_data: dict[str, Any], request_path: Path) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "send",
            str(run_data["channel"]),
            "--scope",
            str(run_data["scope"]),
            "--as",
            "claude",
            "--to",
            str(run_data["agent"]),
            "--text-file",
            str(request_path),
            "--delivery-mode",
            "requireRunningWorker",
        ]
    )
    update_run(directory, run_data, "running")


def wait_for_run(directory: Path, run_data: dict[str, Any]) -> dict[str, Any]:
    wait_args = [
        "trellis",
        "channel",
        "wait",
        str(run_data["channel"]),
        "--scope",
        str(run_data["scope"]),
        "--as",
        "claude",
        "--to",
        str(run_data["agent"]),
        "--kind",
        "progress,message,done,killed,error",
        "--include-progress",
        "--timeout",
        str(run_data["timeout"]),
    ]
    while True:
        code, wait_output, wait_err = run(wait_args)
        if wait_output:
            print(wait_output)
        try:
            events = sync_messages(directory, run_data)
        except SystemExit:
            update_run(directory, run_data, "failed")
            raise
        status = terminal_status(events)
        update_run(directory, run_data, status or "running")
        if status:
            return run_data
        if code != 0:
            update_run(directory, run_data, "failed")
            command = " ".join(wait_args)
            detail = wait_err or wait_output or f"exit {code}"
            raise SystemExit(f"Command failed: {command}\n{detail}")


def print_run_ledger(run_data: dict[str, Any], *, include_run_id: bool) -> None:
    if include_run_id:
        print(f"Codex run: {run_data['run_id']}", flush=True)
    print(f"channel: {run_data['channel']}", flush=True)
    print(f"status: {run_data['status']}", flush=True)
    print(f"messages: {run_data['messages_path']}", flush=True)


def codex_dispatch(run_kind: str, agent: str, request: Path, timeout: str) -> int:
    if not request.is_file():
        raise SystemExit(f"Request file not found: {request}")
    directory, run_data = make_run(run_kind, agent, request, timeout)
    create_channel(directory, run_data, request)
    spawn_worker(directory, run_data)
    send_request(directory, run_data, request)
    print_run_ledger(run_data, include_run_id=True)
    wait_for_run(directory, run_data)
    print_run_ledger(run_data, include_run_id=False)
    if run_data.get("provider_resume_id"):
        print(f"provider_resume_id: {run_data['provider_resume_id']}")
    return 0


def codex_status(run_id: str) -> int:
    directory = find_run_dir(run_id)
    run_data = load_json(directory / "run.json")
    events = sync_messages(directory, run_data)
    status = terminal_status(events)
    update_run(directory, run_data, status)
    print(f"Codex run: {run_data['run_id']}")
    print(f"channel: {run_data['channel']}")
    print(f"status: {run_data['status']}")
    print(f"last_seq: {run_data['last_seq']}")
    print(f"messages: {run_data['messages_path']}")
    if run_data.get("provider_resume_id"):
        print(f"provider_resume_id: {run_data['provider_resume_id']}")
    return 0


def codex_resume(run_id: str) -> int:
    directory = find_run_dir(run_id)
    run_data = load_json(directory / "run.json")
    if run_data.get("status") in {"done", "failed", "killed"}:
        print(f"Codex run already terminal: {run_data['run_id']}")
        print(f"status: {run_data['status']}")
        print(f"messages: {run_data['messages_path']}")
        return 0
    wait_for_run(directory, run_data)
    print(f"Reattached Codex run: {run_data['run_id']}")
    print(f"channel: {run_data['channel']}")
    print(f"status: {run_data['status']}")
    print(f"messages: {run_data['messages_path']}")
    if run_data.get("provider_resume_id"):
        print(f"provider_resume_id: {run_data['provider_resume_id']}")
    return 0


def default_snapshot_path(kind: str) -> str:
    task = current_task()
    return rel(task / "handoff" / f"{kind}.md")


def workflow_state_block(workflow: str, state: str) -> str | None:
    open_tag = f"[workflow-state:{state}]"
    close_tag = f"[/workflow-state:{state}]"
    open_match = re.search(rf"(?m)^[ \t]*{re.escape(open_tag)}[ \t]*\r?\n", workflow)
    if not open_match:
        return None

    close_match = re.search(
        rf"(?m)^[ \t]*{re.escape(close_tag)}[ \t]*(?:\r?\n|$)",
        workflow[open_match.end():],
    )
    if not close_match:
        return None

    body_start = open_match.end()
    body_end = open_match.end() + close_match.start()
    return workflow[body_start:body_end]


def has_codex_inline_dispatch(config: str) -> bool:
    in_codex_block = False
    for raw_line in config.splitlines():
        line_without_comment = raw_line.split("#", 1)[0]
        stripped = line_without_comment.strip()
        if not stripped:
            continue

        indent = len(line_without_comment) - len(line_without_comment.lstrip(" "))
        if indent == 0:
            in_codex_block = stripped == "codex:"
            continue

        if in_codex_block and stripped == "dispatch_mode: inline":
            return True

    return False


def load_manifest() -> tuple[dict, str | None]:
    path = Path(".trellis") / "headless-codex-pack" / "manifest.json"
    if not path.exists():
        return {}, "manifest missing: .trellis/headless-codex-pack/manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}, "manifest invalid: .trellis/headless-codex-pack/manifest.json"
    if not isinstance(manifest, dict):
        return {}, "manifest invalid: .trellis/headless-codex-pack/manifest.json"
    return manifest, None


def manifest_shape_failures(manifest: dict) -> list[str]:
    failures: list[str] = []
    required = [
        "pack_marker",
        "trellis_version",
        "channel_help",
        "workflow_anchors",
        "managed_files",
    ]
    for key in required:
        if key not in manifest:
            failures.append(f"manifest missing key: {key}")

    if manifest.get("pack_marker") != PACK_MARKER:
        failures.append("manifest pack_marker mismatch")
    if "trellis_version" in manifest and not isinstance(manifest["trellis_version"], dict):
        failures.append("manifest invalid key: trellis_version")
    if "channel_help" in manifest and not isinstance(manifest["channel_help"], dict):
        failures.append("manifest invalid key: channel_help")
    if "workflow_anchors" in manifest and not isinstance(manifest["workflow_anchors"], list):
        failures.append("manifest invalid key: workflow_anchors")
    if "managed_files" in manifest and not isinstance(manifest["managed_files"], list):
        failures.append("manifest invalid key: managed_files")
    return failures


def doctor_manifest_failures(manifest: dict) -> list[str]:
    failures = manifest_shape_failures(manifest)

    for rel_path in manifest.get("managed_files", []):
        if not isinstance(rel_path, str):
            failures.append("manifest invalid managed_files entry")
            continue
        if not Path(rel_path).exists():
            failures.append(f"managed file missing: {rel_path}")

    recorded_version = manifest.get("trellis_version")
    if isinstance(recorded_version, dict) and recorded_version.get("returncode") == 0:
        code, out, err = run(["trellis", "--version"])
        if code != 0:
            failures.append(f"trellis --version failed: {err or out}")
        elif out != recorded_version.get("stdout", ""):
            failures.append("trellis --version changed since install")

    return failures


def install_failures() -> list[str]:
    failures: list[str] = []

    for rel_path, snippets in EXPECTED_SNIPPETS.items():
        path = Path(rel_path)
        if not path.exists():
            failures.append(rel_path)
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet not in text:
                failures.append(f"{rel_path} missing snippet: {snippet}")

    workflow_path = Path(".trellis/workflow.md")
    if not workflow_path.exists():
        failures.append(".trellis/workflow.md")
    else:
        workflow = workflow_path.read_text(encoding="utf-8")
        for snippet in WORKFLOW_SNIPPETS:
            if snippet not in workflow:
                failures.append(f".trellis/workflow.md missing snippet: {snippet}")
        for state, snippet in WORKFLOW_STATE_SNIPPETS.items():
            block = workflow_state_block(workflow, state)
            if block is None or snippet not in block:
                failures.append(f".trellis/workflow.md workflow state guidance missing: {state}")

    config_path = Path(".trellis/config.yaml")
    if not config_path.exists():
        failures.append(".trellis/config.yaml")
    else:
        config = config_path.read_text(encoding="utf-8")
        if not has_codex_inline_dispatch(config):
            failures.append(".trellis/config.yaml codex.dispatch_mode")

    return failures


def verify_install() -> int:
    failures = install_failures()
    if failures:
        print("Install verification failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Install verification passed.")
    return 0


def command_row(rel_path: str, require_dispatch: bool) -> str:
    path = Path(rel_path)
    exists = path.exists()
    has_dispatch = False
    managed = False
    if exists and path.is_file():
        text = path.read_text(encoding="utf-8")
        has_dispatch = "codex-dispatch" in text
        managed = PACK_MARKER in text
    status = "present" if exists else "missing"
    dispatch = "yes" if has_dispatch else "no"
    ownership = "pack-managed" if managed else "native/unmanaged"
    requirement = "required" if require_dispatch else "not-required"
    return f"- {rel_path}: {status}; owner={ownership}; codex-dispatch={dispatch}; dispatch={requirement}"


def report_install() -> int:
    print("Trellis Headless Codex Pack Install Report")
    print()
    print("Command classes:")

    print("Codex-dispatch commands:")
    for rel_path in COMMAND_CLASSES["codex_dispatch_commands"]:
        print(command_row(rel_path, require_dispatch=True))

    print()
    print("Router commands:")
    for rel_path in COMMAND_CLASSES["router_commands"]:
        print(command_row(rel_path, require_dispatch=False))

    print()
    print("Local status commands:")
    for rel_path in COMMAND_CLASSES["local_status_commands"]:
        print(command_row(rel_path, require_dispatch=False))

    print()
    print("Claude-owned commands:")
    for rel_path in COMMAND_CLASSES["claude_owned_commands"]:
        print(command_row(rel_path, require_dispatch=False))

    print()
    print("Native/unmanaged command slots:")
    for rel_path in COMMAND_CLASSES["native_unmanaged_commands"]:
        print(command_row(rel_path, require_dispatch=False))

    print()
    print("Persistent run support:")
    helper = Path(".trellis/scripts/headless_codex_pack.py")
    helper_text = helper.read_text(encoding="utf-8") if helper.exists() else ""
    support_checks = {
        "status": "task_status_report",
        "codex-dispatch": "codex_dispatch",
        "codex-status": "codex_status",
        "codex-resume": "codex_resume",
    }
    for command, symbol in support_checks.items():
        available = symbol in helper_text
        print(f"- {command}: {'available' if available else 'missing'}")
    print("- brainstorm run ledger: .trellis/headless-codex-pack/codex-runs/")
    print("- task run ledger: .trellis/tasks/<task>/handoff/codex-runs/")
    print("- resume behavior: codex-resume <run-id> reattaches without resending the request")

    print()
    print("Verification summary:")
    failures = install_failures()
    if failures:
        print("- verify-install: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("- verify-install: PASS")
    return 0


def doctor() -> int:
    failures: list[str] = []
    manifest, manifest_error = load_manifest()
    if manifest_error:
        failures.append(manifest_error)
    else:
        failures.extend(doctor_manifest_failures(manifest))

    workflow_path = Path(".trellis/workflow.md")
    if not workflow_path.exists():
        failures.append("workflow missing: .trellis/workflow.md")
    else:
        workflow = workflow_path.read_text(encoding="utf-8")
        for anchor in manifest.get("workflow_anchors", []):
            if anchor not in workflow:
                failures.append(f"workflow anchor missing: {anchor}")

    recorded_channel_help = manifest.get("channel_help") if not manifest_error else None
    if not isinstance(recorded_channel_help, dict):
        failures.append("manifest invalid key: channel_help")
        recorded_channel_help = {}

    for subcommand, required_flags in CHANNEL_HELP_REQUIREMENTS.items():
        code, channel_help, channel_err = run(["trellis", "channel", subcommand, "--help"])
        if code != 0:
            failures.append(f"trellis channel {subcommand} --help failed: {channel_err or channel_help}")
            continue
        recorded_help = recorded_channel_help.get(subcommand)
        recorded_flags = recorded_help.get("required_flags") if isinstance(recorded_help, dict) else None
        if recorded_flags != required_flags:
            failures.append(f"manifest channel {subcommand} required_flags mismatch")
        for flag in required_flags:
            if flag not in channel_help:
                failures.append(f"trellis channel {subcommand} missing flag: {flag}")
        if isinstance(recorded_help, dict) and recorded_help.get("returncode") == 0:
            recorded_hash = recorded_help.get("stdout_sha256")
            if recorded_hash and sha256_text(channel_help) != recorded_hash:
                failures.append(f"trellis channel {subcommand} --help changed since install")

    verify_failures = install_failures()
    if verify_failures:
        failures.extend(f"verify-install: {item}" for item in verify_failures)
        failures.append("verify-install failed")

    if failures:
        print("Doctor found issues:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Doctor passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snapshot")
    snap.add_argument("kind", choices=["plan-request", "plan-review-request", "quality-gate-request", "final-gate-request", "implementation-handoff"])
    snap.add_argument("--output")

    brainstorm = sub.add_parser("brainstorm-request")
    brainstorm.add_argument("--prompt", default="")
    brainstorm.add_argument("--output")

    path_cmd = sub.add_parser("snapshot-path")
    path_cmd.add_argument("kind", choices=["plan-request", "plan-review-request", "quality-gate-request", "final-gate-request", "implementation-handoff"])

    dispatch = sub.add_parser("codex-dispatch")
    dispatch.add_argument("--run-kind", required=True, choices=ALL_RUN_KINDS)
    dispatch.add_argument("--agent", required=True)
    dispatch.add_argument("--request", required=True)
    dispatch.add_argument("--timeout", default="30m")

    status = sub.add_parser("codex-status")
    status.add_argument("run_id")

    resume = sub.add_parser("codex-resume")
    resume.add_argument("run_id")

    sub.add_parser("status")
    sub.add_parser("current-task")
    sub.add_parser("verify-install")
    sub.add_parser("report-install")
    sub.add_parser("doctor")
    args = parser.parse_args()

    if args.cmd == "current-task":
        print(rel(current_task()))
        return 0
    if args.cmd == "verify-install":
        return verify_install()
    if args.cmd == "report-install":
        return report_install()
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "status":
        return task_status_report()
    if args.cmd == "snapshot-path":
        print(default_snapshot_path(args.kind))
        return 0
    if args.cmd == "snapshot":
        output = Path(args.output) if args.output else None
        print(snapshot(args.kind, output))
        return 0
    if args.cmd == "brainstorm-request":
        output = Path(args.output) if args.output else None
        print(brainstorm_request(args.prompt, output))
        return 0
    if args.cmd == "codex-dispatch":
        return codex_dispatch(args.run_kind, args.agent, Path(args.request), args.timeout)
    if args.cmd == "codex-status":
        return codex_status(args.run_id)
    if args.cmd == "codex-resume":
        return codex_resume(args.run_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
