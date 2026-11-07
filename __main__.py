"""hartes package — exposes runner.main as __main__ for `python -m hartes`."""
from runner import main
import sys

if __name__ == "__main__":
    sys.exit(main())
