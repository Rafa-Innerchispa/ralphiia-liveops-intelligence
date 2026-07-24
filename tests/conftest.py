import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import reset_liveops_session


@pytest.fixture(autouse=True)
def _isolated_liveops_session():
    reset_liveops_session()
    yield
    reset_liveops_session()
