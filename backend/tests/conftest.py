import os
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Tests exercise template discovery explicitly (see test_fetcher_repo_index).
# Everywhere else the repository index stays off, so a test never depends on
# whether GitHub happens to be reachable from the machine running it.
os.environ.setdefault("TEMPLATE_REPO_INDEX_ENABLED", "false")
