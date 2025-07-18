# File: backend/tools/file_manager_tool.py
# Author: Enhanced MINI S System
# Date: January 17, 2025
# Description: A secure file management tool for agents with sandboxing

import os
import shutil
import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from tools.base_tool import Tool

logger = logging.getLogger(__name__)

class FileManagerTool(Tool):
    """
    A secure file management tool that allows agents to read, write, and manage files
    within a sandboxed workspace directory.
    """
    
    def __init__(self, workspace_root: str = "/tmp/minis_workspace"):
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileManagerTool initialized with workspace: {self.workspace_root}")
    
    @property
    def name(self) -> str:
        return "file_manager"

    @property
    def description(self) -> str:
        return (
            "Manages files within a secure workspace. Can read, write, create, delete, and list files. "
            "All operations are restricted to the agent's workspace directory for security. "
            "Available operations: read, write, create_dir, delete, list, copy, move, exists, get_info. "
            "Input format: {'operation': 'read|write|create_dir|delete|list|copy|move|exists|get_info', "
            "'path': 'relative/path/to/file', 'content': 'file content (for write)', "
            "'destination': 'destination/path (for copy/move)'}"
        )

    def execute(self, operation: str, path: str, content: str = None, destination: str = None, **kwargs) -> str:
        """
        Execute file management operations.
        
        Args:
            operation: The operation to perform
            path: The file/directory path (relative to workspace)
            content: Content for write operations
            destination: Destination path for copy/move operations
            
        Returns:
            str: Result of the operation or error message
        """
        try:
            # Sanitize and validate paths
            safe_path = self._get_safe_path(path)
            if not safe_path:
                return f"Error: Invalid or unsafe path: {path}"
            
            if operation == "read":
                return self._read_file(safe_path)
            elif operation == "write":
                if content is None:
                    return "Error: Content is required for write operation"
                return self._write_file(safe_path, content)
            elif operation == "create_dir":
                return self._create_directory(safe_path)
            elif operation == "delete":
                return self._delete_path(safe_path)
            elif operation == "list":
                return self._list_directory(safe_path)
            elif operation == "copy":
                if destination is None:
                    return "Error: Destination is required for copy operation"
                safe_dest = self._get_safe_path(destination)
                if not safe_dest:
                    return f"Error: Invalid or unsafe destination: {destination}"
                return self._copy_path(safe_path, safe_dest)
            elif operation == "move":
                if destination is None:
                    return "Error: Destination is required for move operation"
                safe_dest = self._get_safe_path(destination)
                if not safe_dest:
                    return f"Error: Invalid or unsafe destination: {destination}"
                return self._move_path(safe_path, safe_dest)
            elif operation == "exists":
                return self._check_exists(safe_path)
            elif operation == "get_info":
                return self._get_file_info(safe_path)
            else:
                return f"Error: Unknown operation '{operation}'. Available operations: read, write, create_dir, delete, list, copy, move, exists, get_info"
                
        except Exception as e:
            error_msg = f"File operation failed: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    def _get_safe_path(self, path: str) -> Path:
        """
        Convert a relative path to a safe absolute path within the workspace.
        Prevents directory traversal attacks.
        """
        try:
            # Remove any leading slashes to ensure relative path
            clean_path = path.lstrip('/')
            
            # Resolve the path within workspace
            full_path = (self.workspace_root / clean_path).resolve()
            
            # Ensure the path is within the workspace
            if not str(full_path).startswith(str(self.workspace_root.resolve())):
                logger.warning(f"Path traversal attempt blocked: {path}")
                return None
            
            return full_path
            
        except Exception as e:
            logger.error(f"Path validation failed for {path}: {e}")
            return None

    def _read_file(self, file_path: Path) -> str:
        """Read content from a file"""
        try:
            if not file_path.exists():
                return f"Error: File does not exist: {file_path.relative_to(self.workspace_root)}"
            
            if not file_path.is_file():
                return f"Error: Path is not a file: {file_path.relative_to(self.workspace_root)}"
            
            # Check file size (limit to 10MB for safety)
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return "Error: File too large (>10MB). Use a different approach for large files."
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Read file: {file_path.relative_to(self.workspace_root)}")
            return f"File content:\n{content}"
            
        except UnicodeDecodeError:
            return "Error: File contains binary data or unsupported encoding"
        except Exception as e:
            return f"Error reading file: {e}"

    def _write_file(self, file_path: Path, content: str) -> str:
        """Write content to a file"""
        try:
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check content size (limit to 10MB)
            if len(content.encode('utf-8')) > 10 * 1024 * 1024:
                return "Error: Content too large (>10MB)"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Wrote file: {file_path.relative_to(self.workspace_root)}")
            return f"Successfully wrote {len(content)} characters to {file_path.relative_to(self.workspace_root)}"
            
        except Exception as e:
            return f"Error writing file: {e}"

    def _create_directory(self, dir_path: Path) -> str:
        """Create a directory"""
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {dir_path.relative_to(self.workspace_root)}")
            return f"Successfully created directory: {dir_path.relative_to(self.workspace_root)}"
            
        except Exception as e:
            return f"Error creating directory: {e}"

    def _delete_path(self, path: Path) -> str:
        """Delete a file or directory"""
        try:
            if not path.exists():
                return f"Error: Path does not exist: {path.relative_to(self.workspace_root)}"
            
            if path.is_file():
                path.unlink()
                logger.info(f"Deleted file: {path.relative_to(self.workspace_root)}")
                return f"Successfully deleted file: {path.relative_to(self.workspace_root)}"
            elif path.is_dir():
                shutil.rmtree(path)
                logger.info(f"Deleted directory: {path.relative_to(self.workspace_root)}")
                return f"Successfully deleted directory: {path.relative_to(self.workspace_root)}"
            else:
                return f"Error: Unknown path type: {path.relative_to(self.workspace_root)}"
                
        except Exception as e:
            return f"Error deleting path: {e}"

    def _list_directory(self, dir_path: Path) -> str:
        """List contents of a directory"""
        try:
            if not dir_path.exists():
                return f"Error: Directory does not exist: {dir_path.relative_to(self.workspace_root)}"
            
            if not dir_path.is_dir():
                return f"Error: Path is not a directory: {dir_path.relative_to(self.workspace_root)}"
            
            items = []
            for item in sorted(dir_path.iterdir()):
                item_type = "DIR" if item.is_dir() else "FILE"
                size = item.stat().st_size if item.is_file() else "-"
                items.append(f"{item_type:4} {size:>10} {item.name}")
            
            if not items:
                return f"Directory is empty: {dir_path.relative_to(self.workspace_root)}"
            
            result = f"Contents of {dir_path.relative_to(self.workspace_root)}:\n"
            result += "TYPE       SIZE NAME\n"
            result += "---- ---------- ----\n"
            result += "\n".join(items)
            
            return result
            
        except Exception as e:
            return f"Error listing directory: {e}"

    def _copy_path(self, src_path: Path, dest_path: Path) -> str:
        """Copy a file or directory"""
        try:
            if not src_path.exists():
                return f"Error: Source does not exist: {src_path.relative_to(self.workspace_root)}"
            
            # Create parent directory of destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if src_path.is_file():
                shutil.copy2(src_path, dest_path)
                logger.info(f"Copied file: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}")
                return f"Successfully copied file: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}"
            elif src_path.is_dir():
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                logger.info(f"Copied directory: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}")
                return f"Successfully copied directory: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}"
            else:
                return f"Error: Unknown path type: {src_path.relative_to(self.workspace_root)}"
                
        except Exception as e:
            return f"Error copying path: {e}"

    def _move_path(self, src_path: Path, dest_path: Path) -> str:
        """Move a file or directory"""
        try:
            if not src_path.exists():
                return f"Error: Source does not exist: {src_path.relative_to(self.workspace_root)}"
            
            # Create parent directory of destination
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(src_path), str(dest_path))
            logger.info(f"Moved: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}")
            return f"Successfully moved: {src_path.relative_to(self.workspace_root)} -> {dest_path.relative_to(self.workspace_root)}"
            
        except Exception as e:
            return f"Error moving path: {e}"

    def _check_exists(self, path: Path) -> str:
        """Check if a path exists"""
        exists = path.exists()
        path_type = ""
        if exists:
            if path.is_file():
                path_type = " (file)"
            elif path.is_dir():
                path_type = " (directory)"
        
        return f"Path {path.relative_to(self.workspace_root)} {'exists' if exists else 'does not exist'}{path_type}"

    def _get_file_info(self, path: Path) -> str:
        """Get detailed information about a file or directory"""
        try:
            if not path.exists():
                return f"Error: Path does not exist: {path.relative_to(self.workspace_root)}"
            
            stat = path.stat()
            info = {
                "path": str(path.relative_to(self.workspace_root)),
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "permissions": oct(stat.st_mode)[-3:]
            }
            
            if path.is_file():
                # Try to detect file type
                suffix = path.suffix.lower()
                if suffix in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.yaml', '.yml']:
                    info["file_type"] = "text"
                elif suffix in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    info["file_type"] = "image"
                elif suffix in ['.mp4', '.avi', '.mov', '.mkv']:
                    info["file_type"] = "video"
                elif suffix in ['.mp3', '.wav', '.flac', '.ogg']:
                    info["file_type"] = "audio"
                else:
                    info["file_type"] = "unknown"
            
            return f"File information:\n{json.dumps(info, indent=2)}"
            
        except Exception as e:
            return f"Error getting file info: {e}"

# Example usage
if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()
    
    tool = FileManagerTool()
    
    # Test operations
    print("=== Testing File Manager Tool ===")
    
    # Create a test file
    result = tool.execute("write", "test.txt", "Hello, World!")
    print(f"Write: {result}")
    
    # Read the file
    result = tool.execute("read", "test.txt")
    print(f"Read: {result}")
    
    # List directory
    result = tool.execute("list", ".")
    print(f"List: {result}")
    
    # Get file info
    result = tool.execute("get_info", "test.txt")
    print(f"Info: {result}")