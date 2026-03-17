

import sys
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
DATA_DIR = os.path.join(REPO_ROOT, "data")
PFALL_FILE = os.path.join(DATA_DIR, "PFALL24.txt")
DB_FILE = os.path.join(DATA_DIR, "prices.db")


sys.path.insert(0, SRC_DIR)


@pytest.fixture(autouse=True)
def _chdir_to_src(monkeypatch):
    """pricer.py references ../data/ relative to cwd; run from src/."""
    monkeypatch.chdir(SRC_DIR)



# load_data tests

class TestLoadData:
    """Tests for pricer.load_data()."""

    def test_load_data_real_file(self):
        from pricer import load_data
        result = load_data(PFALL_FILE)
        assert result is True
        assert os.path.isfile(DB_FILE), "prices.db should be created after load_data"

    def test_load_data_missing_file(self):
        from pricer import load_data
        result = load_data(os.path.join(DATA_DIR, "NONEXISTENT.txt"))
        assert result is False



# code_price tests — valid lookups

class TestCodePriceValid:
    """Verify known HCPCS codes return correct facility fees."""

    @pytest.fixture(autouse=True)
    def _ensure_db(self):
        """Make sure prices.db exists before running price lookups."""
        if not os.path.isfile(DB_FILE):
            from pricer import load_data
            load_data(PFALL_FILE)

    def test_code_0446T_default(self):
        from pricer import code_price
        result = code_price("0446T", "00", "15202")
        assert result is not None
        assert not result.empty
        fee = float(result.iloc[0]["Facility Fee Schedule Amount"])
        assert fee == pytest.approx(53.72, abs=0.01)

    def test_code_99213_em(self):
        from pricer import code_price
        result = code_price("99213", "00", "15202")
        assert result is not None
        assert not result.empty
        fee = float(result.iloc[0]["Facility Fee Schedule Amount"])
        assert fee == pytest.approx(62.65, abs=0.01)

    def test_code_G0011_gcode(self):
        from pricer import code_price
        result = code_price("G0011", "00", "15202")
        assert result is not None
        assert not result.empty
        fee = float(result.iloc[0]["Facility Fee Schedule Amount"])
        assert fee == pytest.approx(21.42, abs=0.01)

    def test_code_G0011_different_carrier(self):
        from pricer import code_price
        result = code_price("G0011", "05", "01112")
        assert result is not None
        assert not result.empty
        fee = float(result.iloc[0]["Facility Fee Schedule Amount"])
        assert fee == pytest.approx(25.30, abs=0.01)


# code_price tests — invalid / edge-case lookups

class TestCodePriceInvalid:
    """Verify that bad inputs return empty DataFrames or None."""

    @pytest.fixture(autouse=True)
    def _ensure_db(self):
        if not os.path.isfile(DB_FILE):
            from pricer import load_data
            load_data(PFALL_FILE)

    def test_wrong_hcpcs_code(self):
        from pricer import code_price
        result = code_price("ZZZZZ", "00", "15202")
        assert result is not None
        assert result.empty

    def test_wrong_locality(self):
        from pricer import code_price
        result = code_price("0446T", "99", "15202")
        assert result is not None
        assert result.empty

    def test_wrong_carrier(self):
        from pricer import code_price
        result = code_price("0446T", "00", "00000")
        assert result is not None
        assert result.empty

    def test_empty_string_code(self):
        from pricer import code_price
        result = code_price("", "00", "15202")
        assert result is not None
        assert result.empty

    def test_missing_db_file(self, tmp_path, monkeypatch):
        """When prices.db doesn't exist, code_price should return None."""
        # chdir to a temp directory where ../data/prices.db won't exist
        temp_src = tmp_path / "src"
        temp_src.mkdir()
        monkeypatch.chdir(temp_src)
        from pricer import code_price
        result = code_price("0446T", "00", "15202")
        assert result is None
