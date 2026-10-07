import sys
import os

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.python_runner import python_sandbox
from core.slack_formatter import markdown_to_slack

def run_phase6_verification():
    print("\n=======================================================")
    print("       ⚡ SYNAPSE PHASE 6: PYTHON SANDBOX & FULL ENGINE ")
    print("=======================================================\n")

    # 1. Test Python Sandbox Code Execution
    print("🔍 [1/3] Testing Autonomous Python Sandbox Execution...")
    sample_code = """
import time
start = time.time()
nodes = [f"node_{i}" for i in range(10000)]
elapsed = time.time() - start
print(f"AST Benchmark: Processed {len(nodes)} nodes in {elapsed*1000:.2f}ms")
"""
    res = python_sandbox.execute_code(sample_code)
    print(f"   • Success:   {res['success']}")
    print(f"   • Exit Code: {res['exit_code']}")
    print(f"   • Output:    {res['stdout']}")
    assert res['success'] is True, f"❌ Sandbox execution failed: {res['error']}"
    assert "AST Benchmark:" in res['stdout'], "❌ Expected stdout missing"
    print("   ✅ Python Subprocess Sandbox PASSED.\n")

    # 2. Test Sandbox Security & Timeout Protection
    print("🔍 [2/3] Testing Sandbox Security & Timeout Guardrails...")
    
    # Test forbidden command
    bad_code = "import os; os.system('rm -rf /tmp/test')"
    bad_res = python_sandbox.execute_code(bad_code)
    assert bad_res['success'] is False, "❌ Sandbox failed to block dangerous command"
    print("   • Destructive command blocking: Verified.")

    # Test timeout protection
    timeout_code = "import time; time.sleep(20)"
    short_sandbox = python_sandbox.__class__(timeout_seconds=2)
    timeout_res = short_sandbox.execute_code(timeout_code)
    assert timeout_res['success'] is False, "❌ Sandbox failed to enforce timeout"
    print("   • Hard timeout enforcement: Verified.")
    print("   ✅ Security & Timeout Guardrails PASSED.\n")

    # 3. Test Slack Formatter (No Asterisk Artifacts)
    print("🔍 [3/3] Testing Native Slack Formatter Conversion...")
    raw_md = "### Core Finding\n**Elena** proposed a `Rust` pipeline with **0.5%** false positive rate."
    slack_formatted = markdown_to_slack(raw_md)
    print(f"   • Raw Input:       {repr(raw_md)}")
    print(f"   • Formatted Output:\n{slack_formatted}")
    assert "**" not in slack_formatted, "❌ Double asterisks still present in formatted output"
    assert "*Core Finding*" in slack_formatted, "❌ Header conversion failed"
    print("   ✅ Native Slack Formatting PASSED.\n")

    print("=======================================================")
    print("  🎉 PHASE 6 VERIFICATION 100% COMPLETE & PASSING!   ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_phase6_verification()
