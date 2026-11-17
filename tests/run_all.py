"""Run every test file (each in its own process). Usage:  py tests/run_all.py"""
import subprocess, sys
from pathlib import Path

here = Path(__file__).parent
failed = 0
for f in sorted(here.glob("test_*.py")):
    print(f"\n=== {f.name} ===")
    failed += subprocess.call([sys.executable, str(f)]) != 0
print("\nALL TESTS PASSED" if not failed else f"\n{failed} TEST FILE(S) FAILED")
sys.exit(1 if failed else 0)
