from __future__ import annotations

import pytest
from fake_hedgedoc import FakeHedgeDoc


@pytest.fixture
def hedgedoc():
    """A running fake HedgeDoc 1.x instance; tweak its attributes to change behaviour."""
    hd = FakeHedgeDoc()
    yield hd
    hd.close()
