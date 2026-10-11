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
import shutil
from pathlib import Path

from core.agent.schemas import ToolDefinition, ToolParameter, ToolResult
from core.logging import get_logger

logger = get_logger(__name__)


# Tool Definitions

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

SEARCH_FILES_DEF = ToolDefinition(
    name="search_files",
    description=(
        "Search for files inside a directory by name or pattern using glob. "
        "Use this to find files when you know part of the name or the extension."
    ),
    parameters={
        "path": ToolParameter(
            type="string",
            description="The absolute path to the directory to search in (e.g., '/home/user').",
            required=True,
        ),
        "pattern": ToolParameter(
            type="string",
            description="The glob pattern to search for (e.g., '*.md', '*config*').",
            required=True,
        ),
    },
    category="files",
)

MOVE_FILE_DEF = ToolDefinition(
    name="move_file",
    description="Move or rename a file or directory on the file system.",
    parameters={
        "source": ToolParameter(
            type="string",
            description="Absolute path to the source file or directory.",
            required=True,
        ),
        "destination": ToolParameter(
            type="string",
            description="Absolute path to the destination.",
            required=True,
        ),
    },
    category="files",
)

COPY_FILE_DEF = ToolDefinition(
    name="copy_file",
    description="Copy a file or directory to a new location on the file system.",
    parameters={
        "source": ToolParameter(
            type="string",
            description="Absolute path to the source file or directory.",
            required=True,
        ),
        "destination": ToolParameter(
            type="string",
            description="Absolute path to the destination.",
            required=True,
        ),
    },
    category="files",
)

DELETE_FILE_DEF = ToolDefinition(
    name="delete_file",
    description="Delete a file or directory from the file system.",
    parameters={
        "path": ToolParameter(
            type="string",
            description="Absolute path to the file or directory to delete.",
            required=True,
        ),
    },
    category="files",
)

# Tool Implementations

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


def search_files(path: str, pattern: str) -> ToolResult:
    """Search for files matching a glob pattern."""
    logger.info("tool_search_files", path=path, pattern=pattern)
    
    expanded_path = os.path.expanduser(path)
    if not os.path.isdir(expanded_path):
        return ToolResult(
            tool_name="search_files",
            success=False,
            error=f"Directory not found: {path}",
        )
        
    try:
        p = Path(expanded_path)
        # recursive search
        matches = list(p.rglob(pattern))
        
        # Limit results if there are too many
        MAX_RESULTS = 50
        truncated = len(matches) > MAX_RESULTS
        matches = matches[:MAX_RESULTS]
        
        output = f"Search results for '{pattern}' in {path}:\n\n"
        output += "\n".join(f"- {m.absolute()}" for m in matches) if matches else "- (no matches found)"
        if truncated:
            output += f"\n\n... (results truncated to {MAX_RESULTS} items)"
            
        return ToolResult(
            tool_name="search_files",
            success=True,
            data={"path": path, "pattern": pattern, "count": len(matches)},
            display_text=output,
        )
    except Exception as e:
        logger.error("tool_search_files_failed", path=path, error=str(e))
        return ToolResult(
            tool_name="search_files",
            success=False,
            error=f"Failed to search files: {str(e)}",
        )


def move_file(source: str, destination: str) -> ToolResult:
    """Move or rename a file or directory."""
    logger.info("tool_move_file", source=source, destination=destination)
    
    src = os.path.expanduser(source)
    dst = os.path.expanduser(destination)
    
    if not os.path.exists(src):
        return ToolResult(
            tool_name="move_file",
            success=False,
            error=f"Source not found: {source}",
        )
        
    try:
        shutil.move(src, dst)
        return ToolResult(
            tool_name="move_file",
            success=True,
            data={"source": source, "destination": destination},
            display_text=f"Moved '{source}' to '{destination}'.",
        )
    except Exception as e:
        logger.error("tool_move_file_failed", source=source, error=str(e))
        return ToolResult(
            tool_name="move_file",
            success=False,
            error=f"Failed to move: {str(e)}",
        )


def copy_file(source: str, destination: str) -> ToolResult:
    """Copy a file or directory."""
    logger.info("tool_copy_file", source=source, destination=destination)
    
    src = os.path.expanduser(source)
    dst = os.path.expanduser(destination)
    
    if not os.path.exists(src):
        return ToolResult(
            tool_name="copy_file",
            success=False,
            error=f"Source not found: {source}",
        )
        
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
            
        return ToolResult(
            tool_name="copy_file",
            success=True,
            data={"source": source, "destination": destination},
            display_text=f"Copied '{source}' to '{destination}'.",
        )
    except Exception as e:
        logger.error("tool_copy_file_failed", source=source, error=str(e))
        return ToolResult(
            tool_name="copy_file",
            success=False,
            error=f"Failed to copy: {str(e)}",
        )


def delete_file(path: str) -> ToolResult:
    """Delete a file or directory."""
    logger.info("tool_delete_file", path=path)
    
    tgt = os.path.expanduser(path)
    
    if not os.path.exists(tgt):
        return ToolResult(
            tool_name="delete_file",
            success=False,
            error=f"Path not found: {path}",
        )
        
    try:
        if os.path.isdir(tgt):
            shutil.rmtree(tgt)
        else:
            os.remove(tgt)
            
        return ToolResult(
            tool_name="delete_file",
            success=True,
            data={"path": path},
            display_text=f"Deleted '{path}'.",
        )
    except Exception as e:
        logger.error("tool_delete_file_failed", path=path, error=str(e))
        return ToolResult(
            tool_name="delete_file",
            success=False,
            error=f"Failed to delete: {str(e)}",
        )
