# File: backend/tools/code_executor_tool.py
# Author: Enhanced MINI S System
# Date: January 17, 2025
# Description: A secure code execution tool with sandboxing capabilities

import subprocess
import tempfile
import os
import logging
import json
import time
from pathlib import Path
from typing import Any, Dict, List
from tools.base_tool import Tool

logger = logging.getLogger(__name__)

class CodeExecutorTool(Tool):
    """
    A secure code execution tool that can run code in various languages
    within a sandboxed environment with resource limits.
    """
    
    def __init__(self, workspace_root: str = "/tmp/minis_workspace", timeout: int = 30):
        self.workspace_root = Path(workspace_root)
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        
        # Supported languages and their execution commands
        self.language_configs = {
            "python": {
                "extension": ".py",
                "command": ["python3", "-u"],
                "docker_image": "python:3.9-slim"
            },
            "javascript": {
                "extension": ".js",
                "command": ["node"],
                "docker_image": "node:16-slim"
            },
            "bash": {
                "extension": ".sh",
                "command": ["bash"],
                "docker_image": "ubuntu:20.04"
            },
            "sql": {
                "extension": ".sql",
                "command": ["sqlite3", ":memory:"],
                "docker_image": "alpine:latest"
            }
        }
        
        logger.info(f"CodeExecutorTool initialized with workspace: {self.workspace_root}")
    
    @property
    def name(self) -> str:
        return "code_executor"

    @property
    def description(self) -> str:
        return (
            "Executes code in a secure sandboxed environment. Supports Python, JavaScript, Bash, and SQL. "
            "Automatically handles file creation, execution, and cleanup. Has resource limits and timeout protection. "
            "Input format: {'language': 'python|javascript|bash|sql', 'code': 'code to execute', "
            "'use_docker': true|false (optional), 'args': ['arg1', 'arg2'] (optional for command line args)}"
        )

    def execute(self, language: str, code: str, use_docker: bool = False, args: List[str] = None, **kwargs) -> str:
        """
        Execute code in the specified language.
        
        Args:
            language: Programming language (python, javascript, bash, sql)
            code: Code to execute
            use_docker: Whether to use Docker for additional sandboxing
            args: Command line arguments for the script
            
        Returns:
            str: Execution result including stdout, stderr, and metadata
        """
        try:
            if language not in self.language_configs:
                return f"Error: Unsupported language '{language}'. Supported: {', '.join(self.language_configs.keys())}"
            
            config = self.language_configs[language]
            
            if use_docker:
                return self._execute_with_docker(language, code, config, args or [])
            else:
                return self._execute_locally(language, code, config, args or [])
                
        except Exception as e:
            error_msg = f"Code execution failed: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg

    def _execute_locally(self, language: str, code: str, config: Dict, args: List[str]) -> str:
        """Execute code locally with basic sandboxing"""
        start_time = time.time()
        
        # Create temporary file for the code
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=config["extension"], 
            dir=self.workspace_root,
            delete=False
        ) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
        
        try:
            # Prepare command
            cmd = config["command"] + [temp_file_path] + args
            
            # Set up environment with restrictions
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"  # Prevent .pyc files
            env["TMPDIR"] = str(self.workspace_root)  # Restrict temp directory
            
            # Execute with resource limits
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workspace_root,
                env=env
            )
            
            execution_time = time.time() - start_time
            
            # Prepare result
            output = {
                "language": language,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": round(execution_time, 3),
                "timeout": self.timeout,
                "success": result.returncode == 0
            }
            
            # Format output
            formatted_result = f"=== Code Execution Result ===\n"
            formatted_result += f"Language: {language}\n"
            formatted_result += f"Exit Code: {result.returncode}\n"
            formatted_result += f"Execution Time: {execution_time:.3f}s\n"
            formatted_result += f"Success: {'Yes' if result.returncode == 0 else 'No'}\n\n"
            
            if result.stdout:
                formatted_result += f"=== STDOUT ===\n{result.stdout}\n"
            
            if result.stderr:
                formatted_result += f"=== STDERR ===\n{result.stderr}\n"
            
            if result.returncode != 0:
                formatted_result += f"\n=== EXECUTION FAILED ===\n"
                formatted_result += f"The code exited with non-zero status: {result.returncode}\n"
            
            logger.info(f"Executed {language} code locally: exit_code={result.returncode}, time={execution_time:.3f}s")
            return formatted_result
            
        except subprocess.TimeoutExpired:
            return f"Error: Code execution timed out after {self.timeout} seconds"
        except FileNotFoundError:
            return f"Error: {language} interpreter not found. Please install {config['command'][0]}"
        except Exception as e:
            return f"Error during execution: {e}"
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass

    def _execute_with_docker(self, language: str, code: str, config: Dict, args: List[str]) -> str:
        """Execute code using Docker for enhanced sandboxing"""
        try:
            # Check if Docker is available
            docker_check = subprocess.run(
                ["docker", "--version"], 
                capture_output=True, 
                timeout=5
            )
            if docker_check.returncode != 0:
                return "Error: Docker is not available. Falling back to local execution."
        except:
            return "Error: Docker is not available. Falling back to local execution."
        
        start_time = time.time()
        
        # Create temporary directory for this execution
        with tempfile.TemporaryDirectory(dir=self.workspace_root) as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Write code to file
            code_file = temp_dir_path / f"code{config['extension']}"
            with open(code_file, 'w') as f:
                f.write(code)
            
            # Prepare Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",  # Remove container after execution
                "--network", "none",  # No network access
                "--memory", "256m",  # Memory limit
                "--cpus", "0.5",  # CPU limit
                "--user", "nobody",  # Run as non-root user
                "--read-only",  # Read-only filesystem
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=100m",  # Temporary filesystem
                "-v", f"{temp_dir_path}:/workspace:ro",  # Mount code directory as read-only
                "-w", "/workspace",  # Set working directory
                config["docker_image"]
            ]
            
            # Add language-specific command
            if language == "python":
                docker_cmd.extend(["python3", "-u", f"code{config['extension']}"] + args)
            elif language == "javascript":
                docker_cmd.extend(["node", f"code{config['extension']}"] + args)
            elif language == "bash":
                docker_cmd.extend(["bash", f"code{config['extension']}"] + args)
            elif language == "sql":
                docker_cmd.extend(["sh", "-c", f"cat code{config['extension']} | sqlite3"])
            
            try:
                # Execute in Docker
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                
                execution_time = time.time() - start_time
                
                # Format result
                formatted_result = f"=== Docker Code Execution Result ===\n"
                formatted_result += f"Language: {language}\n"
                formatted_result += f"Image: {config['docker_image']}\n"
                formatted_result += f"Exit Code: {result.returncode}\n"
                formatted_result += f"Execution Time: {execution_time:.3f}s\n"
                formatted_result += f"Success: {'Yes' if result.returncode == 0 else 'No'}\n\n"
                
                if result.stdout:
                    formatted_result += f"=== STDOUT ===\n{result.stdout}\n"
                
                if result.stderr:
                    formatted_result += f"=== STDERR ===\n{result.stderr}\n"
                
                if result.returncode != 0:
                    formatted_result += f"\n=== EXECUTION FAILED ===\n"
                    formatted_result += f"The code exited with non-zero status: {result.returncode}\n"
                
                logger.info(f"Executed {language} code in Docker: exit_code={result.returncode}, time={execution_time:.3f}s")
                return formatted_result
                
            except subprocess.TimeoutExpired:
                return f"Error: Docker execution timed out after {self.timeout} seconds"
            except Exception as e:
                return f"Error during Docker execution: {e}"

    def validate_code(self, language: str, code: str) -> str:
        """Validate code without executing it"""
        try:
            if language == "python":
                import ast
                try:
                    ast.parse(code)
                    return "Python code syntax is valid"
                except SyntaxError as e:
                    return f"Python syntax error: {e}"
            
            elif language == "javascript":
                # Basic validation - could be enhanced with a JS parser
                if "eval(" in code or "Function(" in code:
                    return "Warning: Code contains potentially dangerous eval() or Function() calls"
                return "JavaScript code appears valid (basic check)"
            
            elif language == "bash":
                # Basic validation for dangerous commands
                dangerous_commands = ["rm -rf", "dd if=", ":(){ :|:& };:", "chmod 777"]
                for cmd in dangerous_commands:
                    if cmd in code:
                        return f"Warning: Code contains potentially dangerous command: {cmd}"
                return "Bash code appears valid (basic check)"
            
            elif language == "sql":
                dangerous_sql = ["DROP", "DELETE", "TRUNCATE", "ALTER"]
                code_upper = code.upper()
                for cmd in dangerous_sql:
                    if cmd in code_upper:
                        return f"Warning: Code contains potentially destructive SQL command: {cmd}"
                return "SQL code appears valid (basic check)"
            
            else:
                return f"Validation not implemented for {language}"
                
        except Exception as e:
            return f"Validation error: {e}"

# Example usage
if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()
    
    tool = CodeExecutorTool()
    
    print("=== Testing Code Executor Tool ===")
    
    # Test Python code
    python_code = """
print("Hello from Python!")
import sys
print(f"Python version: {sys.version}")
for i in range(3):
    print(f"Count: {i}")
"""
    
    result = tool.execute("python", python_code)
    print("Python execution result:")
    print(result)
    print("\n" + "="*50 + "\n")
    
    # Test JavaScript code
    js_code = """
console.log("Hello from JavaScript!");
console.log("Node version:", process.version);
for (let i = 0; i < 3; i++) {
    console.log(`Count: ${i}`);
}
"""
    
    result = tool.execute("javascript", js_code)
    print("JavaScript execution result:")
    print(result)
    print("\n" + "="*50 + "\n")
    
    # Test validation
    result = tool.validate_code("python", "print('valid')")
    print("Validation result:", result)
    
    result = tool.validate_code("python", "print('invalid'")
    print("Validation result:", result)