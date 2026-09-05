"""
tools/files/fs_tools.py

File system tools for NyxAI.

These tools allow the agent to read local files and list directories.
These tools are powerful and require PermissionLevel.CONFIRMATION for sensitive locations,
but we will start with them being generally accessible for productivity.

Tools:
  - list_directory: List the contents of a directory.
  - read_file: Read the contents of a text file.
"""

import os
from pathlib import Path

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)


# ─── Tool Definitions ─────────────────────────────────────────────────────────

LIST_DIRECTORY_DEF = ToolDefinition(
    name="list_directory",
    description=(
        "List the files and folders inside a given directory. "
        "Use this to explore the local file system to find files."
    ),
    parameters={
        "path": ToolParameter(
            type="string",
            description="The absolute path to the directory (e.g., '/home/user/Documents').",
            required=True,
        ),
    },
    category="files",
)

READ_FILE_DEF = ToolDefinition(
    name="read_file",
    description=(
        "Read the contents of a local text file. "
        "Use this to read code, markdown, logs, or plain text files to answer questions."
    ),
    parameters={
        "path": ToolParameter(
            type="string",
            description="The absolute path to the file (e.g., '/home/user/Documents/notes.txt').",
            required=True,
        ),
    },
    category="files",
)


# ─── Tool Implementations ─────────────────────────────────────────────────────

def list_directory(path: str) -> ToolResult:
    """List contents of a directory."""
    logger.info("tool_list_directory", path=path)
    
    expanded_path = os.path.expanduser(path)
    if not os.path.isdir(expanded_path):
        return ToolResult(
            tool_name="list_directory",
            success=False,
            error=f"Directory not found or is not a directory: {path}",
        )
        
    try:
        items = os.listdir(expanded_path)
        # Separate into files and dirs for better context
        dirs = []
        files = []
        for item in sorted(items):
            item_path = os.path.join(expanded_path, item)
            if os.path.isdir(item_path):
                dirs.append(f"{item}/")
            else:
                files.append(item)
                
        output = f"Contents of {path}:\n\nDirectories:\n"
        output += "\n".join(f"- {d}" for d in dirs) if dirs else "- (none)"
        output += "\n\nFiles:\n"
        output += "\n".join(f"- {f}" for f in files) if files else "- (none)"
        
        return ToolResult(
            tool_name="list_directory",
            success=True,
            data={"path": path, "item_count": len(items)},
            display_text=output,
        )
        
    except Exception as e:
        logger.error("tool_list_directory_failed", path=path, error=str(e))
        return ToolResult(
            tool_name="list_directory",
            success=False,
            error=f"Failed to list directory: {str(e)}",
        )


def read_file(path: str) -> ToolResult:
    """Read contents of a text file."""
    logger.info("tool_read_file", path=path)
    
    expanded_path = os.path.expanduser(path)
    if not os.path.isfile(expanded_path):
        return ToolResult(
            tool_name="read_file",
            success=False,
            error=f"File not found or is not a file: {path}",
        )
        
    try:
        # Check size to avoid massive files (limit to ~30KB)
        size = os.path.getsize(expanded_path)
        if size > 30000:
            return ToolResult(
                tool_name="read_file",
                success=False,
                error=f"File is too large to read ({size} bytes). Maximum allowed is 30000 bytes.",
            )
            
        with open(expanded_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return ToolResult(
            tool_name="read_file",
            success=True,
            data={"path": path, "size": size},
            display_text=f"File: {path}\n\n```\n{content}\n```",
        )
        
    except UnicodeDecodeError:
        return ToolResult(
            tool_name="read_file",
            success=False,
            error="File appears to be binary or uses unsupported encoding. Can only read text files.",
        )
    except Exception as e:
        logger.error("tool_read_file_failed", path=path, error=str(e))
        return ToolResult(
            tool_name="read_file",
            success=False,
            error=f"Failed to read file: {str(e)}",
        )
