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
START = f"<!-- {PACK_MARKER}:start -->"
END = f"<!-- {PACK_MARKER}:end -->"

EXPECTED_SNIPPETS = {
    ".claude/commands/trellis/codex-brainstorm.md": [
        PACK_MARKER,
        "codex-brainstorm",
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind brainstorm-request",
        "--agent codex-brainstorm",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
        "Do not read\nproject files",
    ],
    ".claude/commands/trellis/codex-plan.md": [
        PACK_MARKER,
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind plan-request",
        "--agent codex-plan",
        "--run-kind plan-review-request",
        "--agent codex-plan-review",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/trellis/codex-continue.md": [
        PACK_MARKER,
        "without overriding native `/trellis:continue`",
        "Slash-command choice selects the implementation adapter",
        "ASCII-only labels",
        "Do not use circled\nnumerals",
        "PHASE_EXIT=$?",
        "continue routing from the printed context unless output is empty or malformed",
        "`status=planning`: run `/tls-plan`",
        "Do not bypass Codex plan review",
        "do not rewrite the native\n`/trellis:continue` contract",
    ],
    ".claude/commands/trellis/implement-codex-plan.md": [
        PACK_MARKER,
        "implementation-handoff",
        "/trellis:codex-quality-gate",
    ],
    ".claude/commands/trellis/codex-quality-gate.md": [
        PACK_MARKER,
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind quality-gate-request",
        "--agent codex-quality-gate",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/trellis/codex-final-gate.md": [
        PACK_MARKER,
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind final-gate-request",
        "--agent codex-final-gate",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/tls-brainstorm.md": [
        PACK_MARKER,
        "/trellis:codex-brainstorm",
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind brainstorm-request",
        "--agent codex-brainstorm",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/tls-plan.md": [
        PACK_MARKER,
        "/trellis:codex-plan",
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind plan-request",
        "--agent codex-plan",
        "--run-kind plan-review-request",
        "--agent codex-plan-review",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/tls-continue.md": [
        PACK_MARKER,
        "/trellis:codex-continue",
        "Slash-command choice selects the implementation adapter",
        "ASCII-only labels",
        "Do not use circled\nnumerals",
        "PHASE_EXIT=$?",
        "continue routing from the printed context unless output is empty or malformed",
        "`status=planning`: run `/tls-plan`",
        "Do not bypass Codex plan review",
        "do not rewrite the native\n`/trellis:continue` contract",
    ],
    ".claude/commands/tls-status.md": [
        PACK_MARKER,
        "headless_codex_pack.py status",
        "reports the Codex adapter's view",
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
        "codex_proxy.sh",
        "--run-kind quality-gate-request",
        "--agent codex-quality-gate",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/tls-final.md": [
        PACK_MARKER,
        "/trellis:codex-final-gate",
        "codex-dispatch",
        "codex_proxy.sh",
        "--run-kind final-gate-request",
        "--agent codex-final-gate",
        "--total-timeout",
        "--lease-timeout",
        "--stale-timeout",
    ],
    ".claude/commands/tls-ask-codex.md": [
        PACK_MARKER,
        "codex-ask",
        "codex_proxy.sh",
        "mktemp -d",
        "PASS",
        "MUST-FIX",
        "BLOCKED",
        "Recommendation",
        "does not create, start, modify,\nor finish Trellis tasks",
    ],
    ".trellis/agents/codex-brainstorm.md": [
        PACK_MARKER,
        "name: codex-brainstorm",
        "provider: codex",
    ],
    ".trellis/agents/codex-ask.md": [
        PACK_MARKER,
        "name: codex-ask",
        "provider: codex",
        "P0",
        "P1",
        "PASS",
        "MUST-FIX",
        "BLOCKED",
        "Recommendation",
        "Do not write files",
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
        "proxy-use",
        "proxy-enabled",
        "proxy-url",
        "codex-ask",
        "codex-dispatch",
        "codex-status",
        "codex-resume",
    ],
    ".trellis/scripts/codex_proxy.sh": [
        PACK_MARKER,
        "proxy-enabled",
        "proxy-url",
        "Codex proxy: disabled",
        "http_proxy",
        "https_proxy",
    ],
}

WORKFLOW_INTERFACE_REQUIRED = [
    "Trellis Workflow Interface",
    "shared Trellis task state machine",
    "Slash-command choice selects the implementation adapter",
    "same `.trellis/tasks/<task>/`",
    "Infer it only from the slash command the user ran",
    "/trellis:continue",
    "/tls-continue",
    "/trellis:codex-continue",
    ".trellis/headless-codex-pack/manifest.json",
    "headless_codex_pack.py report-install",
    "Adapter-specific gates live in the slash command files",
]

WORKFLOW_FORBIDDEN_PHRASES = [
    "This project uses a fixed local collaboration model",
    "Headless Codex owns Phase 1",
    "For the Codex implementation",
    "For Codex-owned commands only",
    "plan-review result says PASS",
    "task.py start` is blocked until headless Codex plan review says PASS",
    "runs the Codex plan/review adapter before the same `task.py start` transition",
    "routes through Claude implementation plus Codex quality/final gates",
]

WORKFLOW_ADAPTER_INVENTORY_COMMANDS = [
    "/tls-brainstorm",
    "/tls-plan",
    "/tls-impl",
    "/tls-quality",
    "/tls-final",
    "/trellis:codex-brainstorm",
    "/trellis:codex-plan",
    "/trellis:implement-codex-plan",
    "/trellis:codex-quality-gate",
    "/trellis:codex-final-gate",
]

TERMINAL_EVENT_KINDS = {"done", "killed", "error"}
TERMINAL_RUN_STATUSES = {"done", "failed", "killed"}
ACTIVITY_EVENT_KINDS = {"progress", "message", "done", "killed", "error", "text"}
WAIT_TIMEOUT_EXIT_CODE = 124
DEFAULT_TOTAL_TIMEOUT = "2h"
DEFAULT_LEASE_TIMEOUT = "5m"
DEFAULT_STALE_TIMEOUT = "15m"
TASK_RUN_KINDS = {
    "plan-request",
    "plan-review-request",
    "quality-gate-request",
    "final-gate-request",
    "implementation-handoff",
}
PACK_RUN_KINDS = {"brainstorm-request"}
ALL_RUN_KINDS = sorted(TASK_RUN_KINDS | PACK_RUN_KINDS)
PROXY_FALSE_VALUES = {"0", "false", "no", "off"}
PROXY_TRUE_VALUES = {"1", "true", "yes", "on"}

ADAPTER_CONTRACT = {
    "interface": "trellis-task-workflow",
    "route_selection": "slash_command",
    "shared_artifacts": ".trellis/tasks/<task>/",
    "status_transition": "task.py start",
    "adapters": {
        "native": {
            "commands": ["/trellis:continue"],
            "owner": "native/unmanaged",
            "contract": "upstream Trellis command files",
        },
        "codex": {
            "commands": ["/tls-continue", "/trellis:codex-continue"],
            "owner": PACK_MARKER,
            "contract": "Codex pack command files",
        },
    },
    "artifact_roles": {
        ".trellis/workflow.md": "interface",
        ".trellis/tasks/<task>/": "shared_artifacts",
        ".claude/commands/trellis/continue.md": "native_adapter",
        ".claude/commands/trellis/codex-continue.md": "codex_adapter",
        ".claude/commands/tls-continue.md": "codex_adapter_alias",
        ".trellis/headless-codex-pack/manifest.json": "adapter_registry",
    },
    "workflow_rules": [
        "workflow_is_interface_only",
        "adapter_specific_gates_live_in_command_files",
        "no_global_codex_gates_for_native_continue",
    ],
}

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
    "ephemeral_codex_commands": [
        ".claude/commands/tls-ask-codex.md",
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


def default_proxy_url() -> str:
    code, out, _ = run(["sh", "-c", "ip route show | grep -i default | awk '{print $3}'"])
    if code != 0:
        return ""
    for line in out.splitlines():
        host_ip = line.strip()
        if host_ip:
            return f"http://{host_ip}:7890"
    return ""


def yaml_top_level_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        without_comment = raw_line.split("#", 1)[0]
        if not without_comment.strip() or without_comment[:1].isspace():
            continue
        if ":" not in without_comment:
            continue
        key, value = without_comment.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value.strip()
    return values


def parse_proxy_bool(value: str, key: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    if normalized in PROXY_TRUE_VALUES:
        return True
    if normalized in PROXY_FALSE_VALUES:
        return False
    raise SystemExit(f"Invalid .trellis/config.yaml {key}: expected true/false, got {value!r}")


def codex_proxy_settings() -> tuple[bool, str]:
    config_path = Path(".trellis") / "config.yaml"
    values: dict[str, str] = {}
    if config_path.exists():
        values = yaml_top_level_values(config_path.read_text(encoding="utf-8"))

    enabled = parse_proxy_bool(values.get("codex-proxy", "false"), "codex-proxy")
    proxy_url = values.get("proxy-url", "").strip() or default_proxy_url()
    if enabled:
        if not proxy_url:
            raise SystemExit(
                ".trellis/config.yaml codex-proxy is true, but proxy-url is empty "
                "and the default gateway proxy URL could not be detected."
            )
        if not proxy_url.startswith(("http://", "https://")):
            raise SystemExit(".trellis/config.yaml proxy-url must start with http:// or https://")
    return enabled, proxy_url


def proxy_enabled_value() -> str:
    enabled, _ = codex_proxy_settings()
    return "1" if enabled else "0"


def proxy_url_value() -> str:
    _, proxy_url = codex_proxy_settings()
    return proxy_url


def proxy_use_from_arguments(arguments: str) -> str:
    _ = arguments
    return proxy_enabled_value()


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
                task = Path(value)
                validation_error = validate_task_path(task)
                if validation_error:
                    raise SystemExit(validation_error)
                return task
    raise SystemExit("No active task. Create a Trellis task first.")


def validate_task_path(task: Path) -> str | None:
    if not task.exists():
        return (
            f"stale active task pointer: {rel(task)} does not exist. "
            "Run `python3 ./.trellis/scripts/task.py start <existing-task-dir>` "
            "or select a current Trellis task before using this Codex adapter."
        )
    if not task.is_dir():
        return f"stale active task pointer: {rel(task)} is not a directory."
    task_json = task / "task.json"
    if not task_json.exists():
        return (
            f"stale active task pointer: {rel(task_json)} is missing. "
            "Run `python3 ./.trellis/scripts/task.py start <existing-task-dir>` "
            "or select a current Trellis task before using this Codex adapter."
        )
    return None


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
                task = Path(value)
                validation_error = validate_task_path(task)
                if validation_error:
                    return None, validation_error
                return task, None
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


def event_text_for_outcome(event: dict[str, Any]) -> str:
    by = str(event.get("by") or event.get("from") or "")
    if by == "claude" or by.startswith("supervisor:"):
        return ""

    parts: list[str] = []
    for key in ("text", "message"):
        value = event.get(key)
        if isinstance(value, str):
            parts.append(value)
    detail = event.get("detail")
    if isinstance(detail, dict):
        value = detail.get("message")
        if isinstance(value, str):
            parts.append(value)
    return "\n".join(parts)


def outcome_from_messages(path: Path) -> str:
    if not path.exists():
        return "unknown"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        text = event_text_for_outcome(event)
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
        if outcome == "unknown" and status in {"killed", "failed"}:
            outcome = status
        return outcome, f"{rel(directory)} ({status})"
    return "missing", "(none)"


def native_route_for_status(status: str) -> str:
    if status == "planning":
        return "/trellis:continue (upstream planning/review/start route on shared artifacts)"
    if status == "in_progress":
        return "/trellis:continue (upstream implement/check/finish route on shared artifacts)"
    if status == "completed":
        return "/trellis:finish-work if the task is not archived yet"
    return "/trellis:continue (upstream Trellis route on shared artifacts)"


def codex_route_items(
    status: str,
    plan_outcome: str,
    quality_outcome: str,
    final_outcome: str,
    implementation_handoff: bool,
) -> list[str]:
    if status == "planning":
        if plan_outcome == "PASS":
            return [
                "shell action: python3 ./.trellis/scripts/task.py start <task-dir>",
                "slash command after start: /tls-impl",
                "why no immediate slash command: activation is a task.py state transition, not a slash-command phase",
                "fallback slash command: /tls-continue",
            ]
        if plan_outcome == "BLOCKED":
            return [
                "slash command: /tls-plan after resolving the blocker",
            ]
        return [
            "slash command: /tls-plan",
        ]
    if status == "in_progress":
        if not implementation_handoff:
            return [
                "slash command: /tls-impl",
            ]
        if quality_outcome != "PASS":
            return [
                "slash command: /tls-quality",
            ]
        if final_outcome != "PASS":
            return [
                "slash command: /tls-final",
            ]
        return [
            "shell action: commit approved files",
            "slash command after commit: /trellis:finish-work",
            "why no immediate slash command: commit is a git operation, not a slash-command phase",
            "fallback slash command: /tls-continue",
        ]
    if status == "completed":
        return [
            "slash command: /trellis:finish-work if the task is not archived yet",
        ]
    return [
        "slash command: /tls-plan if still planning, or /tls-impl if already started",
    ]


def task_status_report() -> int:
    print("Trellis Headless Codex Pack Status")
    print("Adapter: Codex pack view of shared Trellis task artifacts")
    print("Native route: use /trellis:continue for upstream Trellis on the same artifacts")
    print()

    task, task_error = current_task_or_none()
    if task is None:
        print("Active task:")
        print("- path: (none)")
        if task_error:
            print(f"- detail: {task_error}")
        print()
        print("Next:")
        print("- native route: /trellis:continue after selecting or creating an upstream Trellis task")
        print("- codex route: /tls-brainstorm <topic> for exploration, or /tls-plan after task-creation consent")
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
    codex_next_items = codex_route_items(
        status,
        plan_outcome,
        quality_outcome,
        final_outcome,
        implementation_handoff,
    )

    print()
    print("Routes:")
    print(f"- shared state: {status}")
    print(f"- native route: {native_route_for_status(status)}")
    print("- codex route:")
    for item in codex_next_items:
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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def duration_seconds(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.fullmatch(r"(\d+)(ms|s|m|h)?", text)
    if not match:
        raise SystemExit(f"Invalid duration: {text}")
    amount = int(match.group(1))
    unit = match.group(2) or "s"
    if unit == "ms":
        return amount / 1000
    if unit == "s":
        return float(amount)
    if unit == "m":
        return float(amount * 60)
    if unit == "h":
        return float(amount * 3600)
    raise SystemExit(f"Invalid duration: {text}")


def elapsed_seconds(started_at: Any, now: datetime | None = None) -> float | None:
    started = parse_utc(started_at)
    if started is None:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0.0, (current - started).total_seconds())


def format_seconds(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    seconds = int(max(0, value))
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


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


def make_run(
    run_kind: str,
    agent: str,
    request_path: Path,
    total_timeout: str,
    lease_timeout: str = DEFAULT_LEASE_TIMEOUT,
    stale_timeout: str = DEFAULT_STALE_TIMEOUT,
) -> tuple[Path, dict[str, Any]]:
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
        "timeout": total_timeout,
        "total_timeout": total_timeout,
        "lease_timeout": lease_timeout,
        "stale_timeout": stale_timeout,
        "status": "created",
        "health": "alive_silent",
        "last_seq": 0,
        "last_activity_at": None,
        "last_terminal_at": None,
        "last_health_check_at": now,
        "silent_for_seconds": 0,
        "exit_reason": None,
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
    observed_activity = record_event_activity(run_data, events)
    refresh_health(run_data, observed_activity=observed_activity)
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


def event_timestamp(event: dict[str, Any], fallback: str) -> str:
    value = event.get("ts")
    return value if isinstance(value, str) and value.strip() else fallback


def record_event_activity(run_data: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    now = utc_now()
    observed = False
    for event in events:
        kind = event_kind(event)
        if kind not in ACTIVITY_EVENT_KINDS:
            continue
        observed = True
        event_at = event_timestamp(event, now)
        run_data["last_activity_at"] = event_at
        if kind in TERMINAL_EVENT_KINDS:
            run_data["last_terminal_at"] = event_at
            if kind == "done":
                run_data["exit_reason"] = "done"
            elif kind == "error":
                run_data["exit_reason"] = "error"
            elif kind == "killed":
                reason = event.get("reason")
                run_data["exit_reason"] = reason if isinstance(reason, str) and reason else "killed"
    return observed


def refresh_health(
    run_data: dict[str, Any],
    *,
    observed_activity: bool = False,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(timezone.utc)
    run_data["last_health_check_at"] = current.strftime("%Y-%m-%dT%H:%M:%SZ")
    status = str(run_data.get("status") or "")
    if status in TERMINAL_RUN_STATUSES:
        run_data["health"] = "expired" if run_data.get("exit_reason") == "total_timeout" else "terminal"
        return
    if observed_activity:
        run_data["health"] = "healthy"
        run_data["silent_for_seconds"] = 0
        return
    last_activity_at = run_data.get("last_activity_at") or run_data.get("created_at")
    silent_for = elapsed_seconds(last_activity_at, current)
    if silent_for is not None:
        run_data["silent_for_seconds"] = int(silent_for)
    stale_timeout = duration_seconds(run_data.get("stale_timeout") or DEFAULT_STALE_TIMEOUT)
    if silent_for is not None and stale_timeout is not None and stale_timeout > 0 and silent_for >= stale_timeout:
        run_data["health"] = "stale"
    else:
        run_data["health"] = "alive_silent"


def total_timeout_seconds(run_data: dict[str, Any]) -> float | None:
    # Old ledgers did not distinguish hard timeout from wait timeout. Do not
    # retroactively hard-kill those runs when a newer helper resumes them.
    if "total_timeout" not in run_data:
        return None
    return duration_seconds(run_data.get("total_timeout"))


def total_timeout_reached(run_data: dict[str, Any]) -> bool:
    total = total_timeout_seconds(run_data)
    if total is None or total <= 0:
        return False
    elapsed = elapsed_seconds(run_data.get("created_at"))
    return elapsed is not None and elapsed >= total


def run_command_failure(args: list[str], code: int, out: str, err: str) -> str:
    command = " ".join(args)
    detail = err or out or f"exit {code}"
    return f"Command failed: {command}\n{detail}"


def update_run(
    directory: Path,
    run_data: dict[str, Any],
    status: str | None = None,
    *,
    observed_activity: bool = False,
) -> None:
    if status is not None:
        run_data["status"] = status
    refresh_health(run_data, observed_activity=observed_activity)
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
    total_timeout = run_data.get("total_timeout") or run_data.get("timeout") or DEFAULT_TOTAL_TIMEOUT
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
            str(total_timeout),
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
    while True:
        if total_timeout_reached(run_data):
            expire_run(directory, run_data)
            return run_data
        lease_timeout = run_data.get("lease_timeout") or run_data.get("timeout") or DEFAULT_LEASE_TIMEOUT
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
            str(lease_timeout),
        ]
        code, wait_output, wait_err = run(wait_args)
        if wait_output:
            print(wait_output)
        try:
            events = sync_messages(directory, run_data)
        except SystemExit:
            update_run(directory, run_data, "failed")
            raise
        status = terminal_status(events)
        update_run(directory, run_data, status or "running", observed_activity=bool(events))
        if status:
            return run_data
        if total_timeout_reached(run_data):
            expire_run(directory, run_data)
            return run_data
        if code == WAIT_TIMEOUT_EXIT_CODE:
            update_run(directory, run_data, "running")
            continue
        if code != 0:
            update_run(directory, run_data, "failed")
            raise SystemExit(run_command_failure(wait_args, code, wait_output, wait_err))


def expire_run(directory: Path, run_data: dict[str, Any]) -> None:
    kill_args = [
        "trellis",
        "channel",
        "kill",
        str(run_data["channel"]),
        "--scope",
        str(run_data["scope"]),
        "--as",
        str(run_data["agent"]),
    ]
    code, out, err = run(kill_args)
    if out:
        print(out)
    run_data["exit_reason"] = "total_timeout"
    run_data["health"] = "expired"
    update_run(directory, run_data, "killed")
    if code != 0:
        raise SystemExit(run_command_failure(kill_args, code, out, err))


def print_run_ledger(run_data: dict[str, Any], *, include_run_id: bool) -> None:
    if include_run_id:
        print(f"Codex run: {run_data['run_id']}", flush=True)
    print(f"channel: {run_data['channel']}", flush=True)
    print(f"status: {run_data['status']}", flush=True)
    if run_data.get("health"):
        print(f"health: {run_data['health']}", flush=True)
    if run_data.get("silent_for_seconds") is not None:
        print(f"silent_for: {format_seconds(run_data.get('silent_for_seconds'))}", flush=True)
    print(f"messages: {run_data['messages_path']}", flush=True)


def codex_dispatch(
    run_kind: str,
    agent: str,
    request: Path,
    total_timeout: str,
    lease_timeout: str,
    stale_timeout: str,
) -> int:
    if not request.is_file():
        raise SystemExit(f"Request file not found: {request}")
    directory, run_data = make_run(run_kind, agent, request, total_timeout, lease_timeout, stale_timeout)
    create_channel(directory, run_data, request)
    spawn_worker(directory, run_data)
    send_request(directory, run_data, request)
    print_run_ledger(run_data, include_run_id=True)
    wait_for_run(directory, run_data)
    print_run_ledger(run_data, include_run_id=False)
    if run_data.get("provider_resume_id"):
        print(f"provider_resume_id: {run_data['provider_resume_id']}")
    return 0


def parse_channel_events(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"kind": "text", "message": line}
        if not isinstance(event, dict):
            event = {"kind": "text", "message": line}
        events.append(event)
    return events


def channel_events(channel: str, scope: str, since: int) -> list[dict[str, Any]]:
    out = run_required(
        [
            "trellis",
            "channel",
            "messages",
            channel,
            "--scope",
            scope,
            "--raw",
            "--since",
            str(since),
        ]
    )
    return parse_channel_events(out)


def create_ephemeral_channel(channel: str, agent: str, request_path: Path) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "create",
            channel,
            "--scope",
            "project",
            "--cwd",
            str(Path(".").resolve()),
            "--description",
            f"{PACK_MARKER} ask-codex {agent}",
            "--context-file",
            str(request_path.resolve()),
        ]
    )


def spawn_ephemeral_worker(channel: str, agent: str, total_timeout: str) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "spawn",
            channel,
            "--scope",
            "project",
            "--agent",
            agent,
            "--provider",
            "codex",
            "--as",
            agent,
            "--cwd",
            str(Path(".").resolve()),
            "--timeout",
            total_timeout,
        ]
    )


def send_ephemeral_request(channel: str, agent: str, request_path: Path) -> None:
    run_required(
        [
            "trellis",
            "channel",
            "send",
            channel,
            "--scope",
            "project",
            "--as",
            "claude",
            "--to",
            agent,
            "--text-file",
            str(request_path),
            "--delivery-mode",
            "requireRunningWorker",
        ]
    )


def codex_ask(
    request: Path,
    agent: str,
    total_timeout: str,
    lease_timeout: str,
) -> int:
    if not request.is_file():
        raise SystemExit(f"Request file not found: {request}")

    channel = f"hcx-ask-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
    create_ephemeral_channel(channel, agent, request)
    spawn_ephemeral_worker(channel, agent, total_timeout)
    send_ephemeral_request(channel, agent, request)

    print(f"Codex ask channel: {channel}", flush=True)
    since = 0
    transcript: list[str] = []
    started_at = datetime.now(timezone.utc)
    total_seconds = duration_seconds(total_timeout)
    while True:
        if total_seconds is not None and (datetime.now(timezone.utc) - started_at).total_seconds() >= total_seconds:
            kill_args = [
                "trellis",
                "channel",
                "kill",
                channel,
                "--scope",
                "project",
                "--as",
                agent,
            ]
            code, out, err = run(kill_args)
            if out:
                print(out)
            if code != 0:
                raise SystemExit(run_command_failure(kill_args, code, out, err))
            print("status: killed")
            print("Codex ask expired after total timeout.")
            return 1
        wait_args = [
            "trellis",
            "channel",
            "wait",
            channel,
            "--scope",
            "project",
            "--as",
            "claude",
            "--to",
            agent,
            "--kind",
            "progress,message,done,killed,error",
            "--include-progress",
            "--timeout",
            lease_timeout,
        ]
        code, wait_output, wait_err = run(wait_args)
        if wait_output:
            print(wait_output)
        events = channel_events(channel, "project", since)
        for event in events:
            since = max(since, event_seq(event))
            text = event_text_for_outcome(event).strip()
            if text:
                transcript.append(text)
        status = terminal_status(events)
        if status:
            print("status: " + status)
            if transcript:
                print("Codex ask result:")
                print("\n\n".join(transcript))
            return 0 if status == "done" else 1
        if code == WAIT_TIMEOUT_EXIT_CODE:
            continue
        if code != 0:
            raise SystemExit(run_command_failure(wait_args, code, wait_output, wait_err))


def codex_status(run_id: str) -> int:
    directory = find_run_dir(run_id)
    run_data = load_json(directory / "run.json")
    events = sync_messages(directory, run_data)
    status = terminal_status(events)
    update_run(directory, run_data, status, observed_activity=bool(events))
    print(f"Codex run: {run_data['run_id']}")
    print(f"channel: {run_data['channel']}")
    print(f"status: {run_data['status']}")
    print(f"health: {run_data.get('health', 'unknown')}")
    print(f"silent_for: {format_seconds(run_data.get('silent_for_seconds'))}")
    if run_data.get("last_activity_at"):
        print(f"last_activity_at: {run_data['last_activity_at']}")
    if run_data.get("last_health_check_at"):
        print(f"last_health_check_at: {run_data['last_health_check_at']}")
    print(f"last_seq: {run_data['last_seq']}")
    print(f"messages: {run_data['messages_path']}")
    if run_data.get("provider_resume_id"):
        print(f"provider_resume_id: {run_data['provider_resume_id']}")
    return 0


def codex_resume(run_id: str) -> int:
    directory = find_run_dir(run_id)
    run_data = load_json(directory / "run.json")
    if run_data.get("status") in {"done", "failed", "killed"}:
        refresh_health(run_data)
        save_json(directory / "run.json", run_data)
        print(f"Codex run already terminal: {run_data['run_id']}")
        print(f"status: {run_data['status']}")
        print(f"health: {run_data.get('health', 'unknown')}")
        print(f"messages: {run_data['messages_path']}")
        return 0
    wait_for_run(directory, run_data)
    print(f"Reattached Codex run: {run_data['run_id']}")
    print(f"channel: {run_data['channel']}")
    print(f"status: {run_data['status']}")
    print(f"health: {run_data.get('health', 'unknown')}")
    print(f"silent_for: {format_seconds(run_data.get('silent_for_seconds'))}")
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


def codex_proxy_config_failures(config: str) -> list[str]:
    failures: list[str] = []
    values = yaml_top_level_values(config)

    proxy_enabled = values.get("codex-proxy")
    if proxy_enabled is None:
        failures.append(".trellis/config.yaml codex-proxy")
    else:
        normalized = proxy_enabled.strip().lower()
        if normalized not in PROXY_TRUE_VALUES | PROXY_FALSE_VALUES:
            failures.append(".trellis/config.yaml codex-proxy must be true/false")

    proxy_url = values.get("proxy-url")
    if proxy_url is None:
        failures.append(".trellis/config.yaml proxy-url")
    elif not proxy_url.strip():
        failures.append(".trellis/config.yaml proxy-url")
    elif not proxy_url.startswith(("http://", "https://")):
        failures.append(".trellis/config.yaml proxy-url must start with http:// or https://")

    return failures


def pack_workflow_block(workflow: str) -> str | None:
    if START not in workflow or END not in workflow:
        return None
    _, rest = workflow.split(START, 1)
    block, _ = rest.split(END, 1)
    return block


def pack_state_lines(workflow: str) -> list[str]:
    lines: list[str] = []
    for state in ("planning", "in_progress"):
        block = workflow_state_block(workflow, state)
        if block is None:
            continue
        lines.extend(line for line in block.splitlines() if PACK_MARKER in line)
    return lines


def workflow_contract_failures(workflow: str) -> list[str]:
    failures: list[str] = []
    block = pack_workflow_block(workflow)
    if block is None:
        return [".trellis/workflow.md adapter contract block missing"]

    for token in WORKFLOW_INTERFACE_REQUIRED:
        if token not in block:
            failures.append(f".trellis/workflow.md interface contract missing: {token}")

    for command in WORKFLOW_ADAPTER_INVENTORY_COMMANDS:
        if command in block:
            failures.append(f".trellis/workflow.md interface block contains adapter inventory command: {command}")

    contract_regions = [block, *pack_state_lines(workflow)]
    for phrase in WORKFLOW_FORBIDDEN_PHRASES:
        if any(phrase in region for region in contract_regions):
            failures.append(f".trellis/workflow.md interface leaks adapter implementation: {phrase}")

    for state in ("planning", "in_progress"):
        state_block = workflow_state_block(workflow, state)
        if state_block is None:
            failures.append(f".trellis/workflow.md workflow state missing: {state}")
            continue
        if PACK_MARKER not in state_block:
            failures.append(f".trellis/workflow.md workflow state guidance missing: {state}")
        if "implementation adapter is selected by slash command" not in state_block:
            failures.append(f".trellis/workflow.md workflow state does not select adapter by command: {state}")
        if "native `/trellis:continue` follows upstream Trellis" not in state_block:
            failures.append(f".trellis/workflow.md workflow state missing native adapter route: {state}")
        if "follows the Codex command file for this turn" not in state_block:
            failures.append(f".trellis/workflow.md workflow state missing Codex adapter route: {state}")

    return failures


def adapter_contract_failures(contract: Any) -> list[str]:
    if contract != ADAPTER_CONTRACT:
        return ["manifest adapter_contract mismatch"]
    return []


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
        "adapter_contract",
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
    if "adapter_contract" in manifest:
        failures.extend(adapter_contract_failures(manifest["adapter_contract"]))
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
        failures.extend(workflow_contract_failures(workflow))

    manifest, manifest_error = load_manifest()
    if manifest_error:
        failures.append(manifest_error)
    else:
        failures.extend(manifest_shape_failures(manifest))

    config_path = Path(".trellis/config.yaml")
    if not config_path.exists():
        failures.append(".trellis/config.yaml")
    else:
        config = config_path.read_text(encoding="utf-8")
        if not has_codex_inline_dispatch(config):
            failures.append(".trellis/config.yaml codex.dispatch_mode")
        failures.extend(codex_proxy_config_failures(config))

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
    print("Adapter contract:")
    print(f"- interface: {ADAPTER_CONTRACT['interface']}")
    print(f"- route selection: {ADAPTER_CONTRACT['route_selection']}")
    print(f"- shared artifacts: {ADAPTER_CONTRACT['shared_artifacts']}")
    print(f"- status transition: {ADAPTER_CONTRACT['status_transition']}")
    for name, adapter in ADAPTER_CONTRACT["adapters"].items():
        commands = ", ".join(adapter["commands"])
        print(f"- {name} adapter: {commands}; owner={adapter['owner']}; contract={adapter['contract']}")

    print()
    print("Artifact roles:")
    for path, role in ADAPTER_CONTRACT["artifact_roles"].items():
        print(f"- {path}: {role}")

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
    print("Ephemeral Codex commands:")
    for rel_path in COMMAND_CLASSES["ephemeral_codex_commands"]:
        print(command_row(rel_path, require_dispatch=False))
    print("- ledger: none; uses temporary request files and an ephemeral channel")

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

    proxy_use = sub.add_parser("proxy-use")
    proxy_use.add_argument("--arguments", default="")
    sub.add_parser("proxy-enabled")
    sub.add_parser("proxy-url")

    path_cmd = sub.add_parser("snapshot-path")
    path_cmd.add_argument("kind", choices=["plan-request", "plan-review-request", "quality-gate-request", "final-gate-request", "implementation-handoff"])

    dispatch = sub.add_parser("codex-dispatch")
    dispatch.add_argument("--run-kind", required=True, choices=ALL_RUN_KINDS)
    dispatch.add_argument("--agent", required=True)
    dispatch.add_argument("--request", required=True)
    dispatch.add_argument("--timeout", help="Deprecated alias for --total-timeout")
    dispatch.add_argument("--total-timeout", default=None)
    dispatch.add_argument("--lease-timeout", default=DEFAULT_LEASE_TIMEOUT)
    dispatch.add_argument("--stale-timeout", default=DEFAULT_STALE_TIMEOUT)

    ask = sub.add_parser("codex-ask")
    ask.add_argument("--request", required=True)
    ask.add_argument("--agent", default="codex-ask")
    ask.add_argument("--timeout", help="Deprecated alias for --total-timeout")
    ask.add_argument("--total-timeout", default=None)
    ask.add_argument("--lease-timeout", default=DEFAULT_LEASE_TIMEOUT)

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
    if args.cmd == "proxy-use":
        print(proxy_use_from_arguments(args.arguments))
        return 0
    if args.cmd == "proxy-enabled":
        print(proxy_enabled_value())
        return 0
    if args.cmd == "proxy-url":
        print(proxy_url_value())
        return 0
    if args.cmd == "codex-dispatch":
        total_timeout = args.total_timeout or args.timeout or DEFAULT_TOTAL_TIMEOUT
        duration_seconds(total_timeout)
        duration_seconds(args.lease_timeout)
        duration_seconds(args.stale_timeout)
        return codex_dispatch(
            args.run_kind,
            args.agent,
            Path(args.request),
            total_timeout,
            args.lease_timeout,
            args.stale_timeout,
        )
    if args.cmd == "codex-ask":
        total_timeout = args.total_timeout or args.timeout or "20m"
        duration_seconds(total_timeout)
        duration_seconds(args.lease_timeout)
        return codex_ask(Path(args.request), args.agent, total_timeout, args.lease_timeout)
    if args.cmd == "codex-status":
        return codex_status(args.run_id)
    if args.cmd == "codex-resume":
        return codex_resume(args.run_id)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
