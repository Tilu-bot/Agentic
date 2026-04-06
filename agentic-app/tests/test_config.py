"""
Tests for utils/config.py – validation, coercion, and defaults.
"""
import pytest
from utils.config import _validate_value, _DEFAULT, Config


# ---------------------------------------------------------------------------
# _validate_value unit tests
# ---------------------------------------------------------------------------

class TestValidateValue:

    def test_unknown_key_passes_through(self):
        val, err = _validate_value("nonexistent_key", "anything")
        assert err is None
        assert val == "anything"

    # Bool coercion -----------------------------------------------------------

    def test_bool_true_from_string(self):
        for v in ("true", "True", "TRUE", "1", "yes"):
            coerced, err = _validate_value("quantize_4bit", v)
            assert err is None, f"Expected no error for {v!r}"
            assert coerced is True

    def test_bool_false_from_string(self):
        for v in ("false", "False", "FALSE", "0", "no"):
            coerced, err = _validate_value("quantize_4bit", v)
            assert err is None, f"Expected no error for {v!r}"
            assert coerced is False

    def test_bool_invalid_string_rejected(self):
        _, err = _validate_value("quantize_4bit", "maybe")
        assert err is not None

    def test_bool_from_int(self):
        coerced, err = _validate_value("quantize_4bit", 1)
        assert err is None
        assert coerced is True

    # Int coercion and range --------------------------------------------------

    def test_int_coerced_from_string(self):
        coerced, err = _validate_value("font_size", "14")
        assert err is None
        assert coerced == 14

    def test_int_below_min_rejected(self):
        _, err = _validate_value("font_size", 7)
        assert err is not None

    def test_int_above_max_rejected(self):
        _, err = _validate_value("font_size", 100)
        assert err is not None

    def test_int_at_boundary_accepted(self):
        coerced, err = _validate_value("font_size", 8)
        assert err is None
        assert coerced == 8
        coerced, err = _validate_value("font_size", 32)
        assert err is None
        assert coerced == 32

    def test_int_non_numeric_rejected(self):
        _, err = _validate_value("font_size", "twelve")
        assert err is not None

    # String choices ----------------------------------------------------------

    def test_str_valid_choice_accepted(self):
        for choice in ("auto", "cpu", "cuda", "mps"):
            coerced, err = _validate_value("device", choice)
            assert err is None, f"Expected {choice!r} to be valid"
            assert coerced == choice

    def test_str_invalid_choice_rejected(self):
        _, err = _validate_value("device", "tpu")
        assert err is not None

    def test_str_wrong_type_rejected(self):
        _, err = _validate_value("device", 42)
        assert err is not None

    def test_theme_choices(self):
        _, err = _validate_value("theme", "dark")
        assert err is None
        _, err = _validate_value("theme", "neon")
        assert err is not None

    # skill_retry_budget -------------------------------------------------------

    def test_retry_budget_valid(self):
        for v in (0, 1, 2, 3):
            coerced, err = _validate_value("skill_retry_budget", v)
            assert err is None
            assert coerced == v

    def test_retry_budget_above_max_rejected(self):
        _, err = _validate_value("skill_retry_budget", 4)
        assert err is not None

    def test_retry_budget_below_min_rejected(self):
        _, err = _validate_value("skill_retry_budget", -1)
        assert err is not None

    # context_limit_tokens ----------------------------------------------------

    def test_context_limit_valid(self):
        coerced, err = _validate_value("context_limit_tokens", 8192)
        assert err is None
        assert coerced == 8192

    def test_context_limit_below_min_rejected(self):
        _, err = _validate_value("context_limit_tokens", 256)
        assert err is not None


# ---------------------------------------------------------------------------
# Config singleton – defaults and set() validation
# ---------------------------------------------------------------------------

class TestConfig:

    def test_defaults_present(self):
        c = Config()
        for key in _DEFAULT:
            assert c.get(key) is not None or _DEFAULT[key] is None

    def test_set_valid_value(self):
        c = Config()
        c.set("font_size", 16)
        assert c.get("font_size") == 16

    def test_set_invalid_value_ignored(self):
        c = Config()
        original = c.get("font_size")
        c.set("font_size", "twelve")
        assert c.get("font_size") == original

    def test_update_partial(self):
        c = Config()
        c.update({"font_size": 20, "theme": "light"})
        assert c.get("font_size") == 20
        assert c.get("theme") == "light"

    def test_update_skips_invalid(self):
        c = Config()
        before = c.get("device")
        c.update({"device": "tpu", "font_size": 18})
        assert c.get("device") == before   # bad value rejected
        assert c.get("font_size") == 18    # good value accepted

    def test_skill_retry_budget_default(self):
        c = Config()
        assert c.get("skill_retry_budget") == 1
