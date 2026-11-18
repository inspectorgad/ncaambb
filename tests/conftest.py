import gzip
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FILES = {
    "torvik": "torvik_2027_team_results.csv.gz",
    "haslametrics": "haslametrics_ratings.xml.gz",
    "espn_bpi": "espn_bpi.json.gz",
}


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def raw():
    """raw[source] -> decompressed bytes of the saved download."""
    return {name: gzip.decompress((FIXTURES / f).read_bytes()) for name, f in FILES.items()}
