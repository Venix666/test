from pathlib import Path

import pytest

from halcyon.vanilla import Vanilla

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vanilla"
REAL_VANILLA = ROOT / ".cache" / "bedrock-samples"


@pytest.fixture
def vanilla() -> Vanilla:
    return Vanilla(FIXTURE)


@pytest.fixture
def real_vanilla() -> Vanilla:
    if not (REAL_VANILLA / "resource_pack" / "lighting").is_dir():
        pytest.skip("run tools/fetch_vanilla.sh to test against the real vanilla pack")
    return Vanilla(REAL_VANILLA)
