import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from constraints import check_pair, HARD_BLOCKS, MODIFIER_ALLOWED


# Data-loading sanity checks

class TestDataLoaded:
    """Verify that load_edits() populated both data structures from xlsx."""

    def test_hard_blocks_populated(self):
        assert len(HARD_BLOCKS) > 500_000, (
            f"Expected >500k hard-blocked pairs, got {len(HARD_BLOCKS):,}"
        )

    def test_modifier_allowed_populated(self):
        assert len(MODIFIER_ALLOWED) > 1_000_000, (
            f"Expected >1M modifier-allowed pairs, got {len(MODIFIER_ALLOWED):,}"
        )



# Hard-blocked pair tests

class TestHardBlocked:
    """Pairs with modifier indicator 0 — can NEVER be billed together."""

    def test_hard_blocked_forward(self):
        result = check_pair("0001U", "96523")
        assert result["allowed"] is False
        assert result["modifier"] is None

    def test_hard_blocked_reverse(self):
        result = check_pair("96523", "0001U")
        assert result["allowed"] is False
        assert result["modifier"] is None

    def test_hard_blocked_with_whitespace(self):
        result = check_pair(" 0001U ", " 96523 ")
        assert result["allowed"] is False
        assert result["modifier"] is None



# Modifier-allowed pair tests


class TestModifierAllowed:
    """Pairs with modifier indicator 1 — allowed with appropriate modifier."""

    def test_modifier_allowed_forward(self):
        result = check_pair("0001U", "0029U")
        assert result["allowed"] is True
        assert result["modifier"] == "1"

    def test_modifier_allowed_reverse(self):
        result = check_pair("0029U", "0001U")
        assert result["allowed"] is True
        assert result["modifier"] == "1"



# Unrestricted pair tests


class TestUnrestricted:
    """Pairs with no CCI edit — can be billed together without restrictions."""

    def test_unrestricted_nonexistent_codes(self):
        result = check_pair("99999", "00000")
        assert result["allowed"] is True
        assert result["modifier"] is None

    def test_unrestricted_garbage_codes(self):
        result = check_pair("ZZZZZ", "YYYYY")
        assert result["allowed"] is True
        assert result["modifier"] is None

    def test_unrestricted_same_code(self):
        result = check_pair("99213", "99213")
        assert result["allowed"] is True
        assert result["modifier"] is None

    def test_unrestricted_empty_strings(self):
        result = check_pair("", "")
        assert result["allowed"] is True
        assert result["modifier"] is None



# Return structure tests


class TestReturnStructure:
    """Every check_pair call must return a dict with exactly these keys."""

    EXPECTED_KEYS = {"allowed", "modifier", "reason"}

    def test_keys_hard_blocked(self):
        result = check_pair("0001U", "96523")
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_keys_modifier_allowed(self):
        result = check_pair("0001U", "0029U")
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_keys_unrestricted(self):
        result = check_pair("99999", "00000")
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_reason_is_string(self):
        result = check_pair("0001U", "96523")
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0
