"""
tools/dev/git_tools.py

Autonomous Developer & Git Workflow tools for NyxAI.

Provides:
  - git_status: Inspect branch, modified files, untracked files, and staged changes.
  - git_diff: Inspect unified diff of working tree or staged changes.
  - git_commit: Stage and commit changes with a structured message.
  - git_log: View recent commit history with author, relative timestamp, and subject.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Tool Definitions ───────────────────────────────────────────────────────────

GIT_STATUS_DEF = ToolDefinition(
    name="git_status",
    description=(
        "Get structured Git status for the current repository: current branch, "
        "staged changes, unstaged modifications, and untracked files."
    ),
    parameters={
        "repo_path": ToolParameter(
            type="string",
            description="Optional path to git repository root. Defaults to current project root.",
            required=False,
        ),
    },
    category="terminal",
)

GIT_DIFF_DEF = ToolDefinition(
    name="git_diff",
    description=(
        "Show unified git diff of unstaged or staged code changes. "
        "Useful for inspecting edits, reviewing diffs, and understanding code modifications."
    ),
    parameters={
        "file_path": ToolParameter(
            type="string",
            description="Optional specific file path to diff. If omitted, diffs entire repo.",
            required=False,
        ),
        "staged": ToolParameter(
            type="boolean",
            description="Whether to diff staged changes (--cached). Default is false (working tree).",
            required=False,
        ),
        "repo_path": ToolParameter(
            type="string",
            description="Optional path to git repository root.",
            required=False,
        ),
    },
    category="terminal",
)

GIT_LOG_DEF = ToolDefinition(
    name="git_log",
    description=(
        "View recent Git commit history with commit hashes, authors, dates, and commit messages."
    ),
    parameters={
        "count": ToolParameter(
            type="integer",
            description="Number of commits to return (default: 5, max: 20).",
            required=False,
        ),
        "repo_path": ToolParameter(
            type="string",
            description="Optional path to git repository root.",
            required=False,
        ),
    },
    category="terminal",
)

GIT_COMMIT_DEF = ToolDefinition(
    name="git_commit",
    description=(
        "Create a Git commit with a descriptive message, optionally staging all modified files. "
        "Requires user confirmation under security policy."
    ),
    parameters={
        "message": ToolParameter(
            type="string",
            description="The commit message describing the changes.",
            required=True,
        ),
        "add_all": ToolParameter(
            type="boolean",
            description="Whether to automatically stage all tracked and untracked modifications (git add -A).",
            required=False,
        ),
        "repo_path": ToolParameter(
            type="string",
            description="Optional path to git repository root.",
            required=False,
        ),
    },
    category="terminal",
)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _resolve_repo(repo_path: str | None) -> Path:
    if repo_path:
        p = Path(os.path.expanduser(repo_path)).resolve()
        if p.exists() and p.is_dir():
            return p
    return PROJECT_ROOT


# ── Implementations ────────────────────────────────────────────────────────────

def git_status(repo_path: str | None = None) -> ToolResult:
    """
    Get structured Git status for the repository.
    """
    git_bin = shutil.which("git")
    if not git_bin:
        return ToolResult(tool_name="git_status", success=False, error="git binary not found.")

    cwd = _resolve_repo(repo_path)

    try:
        proc = subprocess.run(
            [git_bin, "status", "--porcelain=v1", "-b"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        if proc.returncode != 0:
            return ToolResult(
                tool_name="git_status",
                success=False,
                error=proc.stderr.strip() or "Not a git repository.",
            )

        lines = proc.stdout.splitlines()
        branch_line = lines[0] if lines else "## Unknown"
        branch_name = branch_line.lstrip("#").strip().split("...")[0].strip()

        staged: list[str] = []
        unstaged: list[str] = []
        untracked: list[str] = []

        for line in lines[1:]:
            if len(line) < 3:
                continue
            index_code = line[0]
            worktree_code = line[1]
            file_path = line[3:].strip()

            if index_code in ("M", "A", "D", "R", "C"):
                staged.append(file_path)
            if worktree_code in ("M", "D"):
                unstaged.append(file_path)
            elif index_code == "?" and worktree_code == "?":
                untracked.append(file_path)

        data = {
            "branch": branch_name,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
        }

        # Format display text
        parts: list[str] = [f"🌿 Branch: **{branch_name}**"]
        if data["is_clean"]:
            parts.append("Working tree is completely clean.")
        else:
            if staged:
                parts.append(f"**Staged ({len(staged)}):**\n" + "\n".join(f"  + {f}" for f in staged[:10]))
            if unstaged:
                parts.append(f"**Modified/Unstaged ({len(unstaged)}):**\n" + "\n".join(f"  * {f}" for f in unstaged[:10]))
            if untracked:
                parts.append(f"**Untracked ({len(untracked)}):**\n" + "\n".join(f"  ? {f}" for f in untracked[:10]))

        return ToolResult(
            tool_name="git_status",
            success=True,
            data=data,
            display_text="\n\n".join(parts),
        )

    except Exception as exc:
        logger.exception("git_status_failed", error=str(exc))
        return ToolResult(tool_name="git_status", success=False, error=str(exc))


def git_diff(
    file_path: str | None = None,
    staged: bool = False,
    repo_path: str | None = None,
) -> ToolResult:
    """
    Show unified git diff of changes.
    """
    git_bin = shutil.which("git")
    if not git_bin:
        return ToolResult(tool_name="git_diff", success=False, error="git binary not found.")

    cwd = _resolve_repo(repo_path)
    cmd: list[str] = [git_bin, "diff"]
    if staged:
        cmd.append("--cached")
    if file_path:
        cmd.append(file_path)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=8.0,
        )

        if proc.returncode != 0:
            return ToolResult(
                tool_name="git_diff",
                success=False,
                error=proc.stderr.strip() or "Failed to run git diff.",
            )

        diff_text = proc.stdout.strip()
        if not diff_text:
            msg = "No changes detected (diff is empty)."
            return ToolResult(
                tool_name="git_diff",
                success=True,
                data={"diff": "", "lines": 0},
                display_text=msg,
            )

        preview = diff_text[:3000]
        if len(diff_text) > 3000:
            preview += f"\n... [Diff truncated: {len(diff_text) - 3000} characters omitted]"

        return ToolResult(
            tool_name="git_diff",
            success=True,
            data={"diff": preview, "total_chars": len(diff_text)},
            display_text=f"```diff\n{preview}\n```",
        )

    except Exception as exc:
        logger.exception("git_diff_failed", error=str(exc))
        return ToolResult(tool_name="git_diff", success=False, error=str(exc))


def git_log(count: int = 5, repo_path: str | None = None) -> ToolResult:
    """
    View recent Git commit history.
    """
    git_bin = shutil.which("git")
    if not git_bin:
        return ToolResult(tool_name="git_log", success=False, error="git binary not found.")

    cwd = _resolve_repo(repo_path)
    num_commits = max(1, min(20, count))

    try:
        proc = subprocess.run(
            [git_bin, "log", f"-n{num_commits}", "--format=%h|%an|%ar|%s"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        if proc.returncode != 0:
            return ToolResult(
                tool_name="git_log",
                success=False,
                error=proc.stderr.strip() or "Failed to read git log.",
            )

        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        commits: list[dict[str, str]] = []
        formatted_list: list[str] = []

        for line in lines:
            parts = line.split("|", 3)
            if len(parts) == 4:
                commit_hash, author, rel_date, subject = parts
                commits.append({
                    "hash": commit_hash,
                    "author": author,
                    "date": rel_date,
                    "subject": subject,
                })
                formatted_list.append(f"• [`{commit_hash}`] **{subject}** ({author}, {rel_date})")

        display = f"📜 Recent {len(commits)} Commits:\n\n" + "\n".join(formatted_list)
        return ToolResult(
            tool_name="git_log",
            success=True,
            data={"commits": commits, "count": len(commits)},
            display_text=display,
        )

    except Exception as exc:
        logger.exception("git_log_failed", error=str(exc))
        return ToolResult(tool_name="git_log", success=False, error=str(exc))


def git_commit(
    message: str,
    add_all: bool = False,
    repo_path: str | None = None,
) -> ToolResult:
    """
    Stage and commit changes with message.
    """
    git_bin = shutil.which("git")
    if not git_bin:
        return ToolResult(tool_name="git_commit", success=False, error="git binary not found.")

    clean_msg = message.strip()
    if not clean_msg:
        return ToolResult(tool_name="git_commit", success=False, error="Commit message cannot be empty.")

    cwd = _resolve_repo(repo_path)

    try:
        if add_all:
            add_proc = subprocess.run(
                [git_bin, "add", "-A"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if add_proc.returncode != 0:
                return ToolResult(
                    tool_name="git_commit",
                    success=False,
                    error=f"git add -A failed: {add_proc.stderr.strip()}",
                )

        commit_proc = subprocess.run(
            [git_bin, "commit", "-m", clean_msg],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=8.0,
        )

        out = commit_proc.stdout.strip()
        err = commit_proc.stderr.strip()

        if commit_proc.returncode != 0:
            return ToolResult(
                tool_name="git_commit",
                success=False,
                error=err or out or "Git commit failed.",
                display_text=f"Git commit failed:\n{err or out}",
            )

        logger.info("git_commit_succeeded", message=clean_msg[:50])
        return ToolResult(
            tool_name="git_commit",
            success=True,
            data={"message": clean_msg, "output": out},
            display_text=f"✅ Changes committed successfully:\n\n{out}",
        )

    except Exception as exc:
        logger.exception("git_commit_failed", error=str(exc))
        return ToolResult(tool_name="git_commit", success=False, error=str(exc))

