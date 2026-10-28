import sys
sys.path.append(".")
import runner
from unittest import mock
import subprocess

def mock_run(*args, **kwargs):
    raise subprocess.CalledProcessError(1, cmd="dummy")

with mock.patch("subprocess.run", mock_run):
    result = runner.run(
        task_name="code_optimizer",
        max_rounds=1,
        model="flash-lite",
        inline_code="def foo(): pass",
        test_command="pytest foo.py"
    )
    print(result)
