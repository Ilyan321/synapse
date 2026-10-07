import sys
import subprocess
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("synapse.sandbox")

class PythonSandbox:
    """
    Autonomous Python Execution Sandbox.
    Safely executes code snippets in an isolated subprocess with a strict timeout.
    """

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def extract_python_code(self, text: str) -> Optional[str]:
        """Extracts python code from ```python ... ``` markdown blocks."""
        pattern = r"```python\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
        return None

    def execute_code(self, code: str) -> Dict[str, Any]:
        """
        Executes Python code in a subprocess and captures stdout/stderr.
        Auto-wraps trailing bare expressions with print() if needed.
        """
        if not code or not code.strip():
            return {"success": False, "error": "Empty code block"}

        # Auto-wrap trailing expression in print() if no print statement exists
        clean_code = code.strip()
        lines = [l for l in clean_code.split("\n") if l.strip()]
        if lines and "print(" not in clean_code:
            last_line = lines[-1].strip()
            if not any(last_line.startswith(kw) for kw in ["import ", "from ", "def ", "class ", "return ", "if ", "for ", "while ", "#"]) and "=" not in last_line:
                lines[-1] = f"print({last_line})"
                clean_code = "\n".join(lines)

        # Block dangerous destructive system calls
        forbidden_terms = ["rm -rf", "shutil.rmtree", "os.system('rm", "mkfs"]
        for term in forbidden_terms:
            if term in clean_code:
                return {
                    "success": False,
                    "error": f"Security restriction: '{term}' is disallowed in sandbox.",
                    "stdout": "",
                    "stderr": "Execution blocked by security policy.",
                    "exit_code": -1
                }

        try:
            logger.info("Executing Python code in sandbox...")
            result = subprocess.run(
                [sys.executable, "-c", clean_code],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            success = (result.returncode == 0)
            return {
                "success": success,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "exit_code": result.returncode,
                "error": None if success else (result.stderr.strip() or f"Process exited with code {result.returncode}")
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"Python sandbox timed out after {self.timeout_seconds}s.")
            return {
                "success": False,
                "error": f"Execution timed out after {self.timeout_seconds} seconds.",
                "stdout": "",
                "stderr": "TimeoutExpired",
                "exit_code": -1
            }
        except Exception as e:
            logger.error(f"Error in Python sandbox execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }

# Singleton instance
python_sandbox = PythonSandbox()
