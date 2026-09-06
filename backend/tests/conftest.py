"""Test configuration.

The suite deliberately covers the decision logic rather than the database
layer: the rules in _decide(), the Stage 4 safety gate and the report period
resolution are where a wrong answer is dangerous, and they are all pure enough
to test without a MySQL instance. Anything needing a live database is exercised
by workers/replay.py against the real one instead.
"""

import sys
from pathlib import Path

# The app imports its own modules flat ("from services import ..."), matching how
# uvicorn is started from inside backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
