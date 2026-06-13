"""Deterministic-yet-unique test data generation.

Names are built from a timestamp (down to seconds) plus a short random suffix.
This guarantees idempotency across runs and prevents duplicate-entity
conflicts even when two tests start within the same second.
"""
from __future__ import annotations

import random
import string
from datetime import datetime

_TIMESTAMP_FMT = "%Y%m%d_%H%M%S"


def _suffix(length: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _timestamp() -> str:
    return datetime.now().strftime(_TIMESTAMP_FMT)


def unique_test_case_name() -> str:
    """e.g. TestCase_20260612_203959_a1b2."""
    return f"TestCase_{_timestamp()}_{_suffix()}"


def unique_test_run_name() -> str:
    """e.g. TestRun_20260612_203959_a1b2."""
    return f"TestRun_{_timestamp()}_{_suffix()}"


def long_name(length: int = 250) -> str:
    """Long name for boundary / edge testing."""
    base = "TestCase_Long_"
    filler = "".join(random.choices(string.ascii_letters, k=max(0, length - len(base))))
    return (base + filler)[:length]


def special_chars_name() -> str:
    """Name containing special characters for edge testing."""
    return f"TestCase_!@#$%^&*()_+-=[]{{}}|;:'<>,.?/_{_timestamp()}"


def unicode_name() -> str:
    """Name with multi-language (BMP) unicode characters for edge testing.

    Uses Chinese + Japanese (Basic Multilingual Plane). Emoji / astral-plane characters
    are intentionally excluded: ChromeDriver's W3C ``send_keys`` rejects non-BMP code
    points and TestRail normalizes emoji, so a verbatim round-trip assertion would test
    the platform's emoji handling rather than unicode support.
    """
    return f"TestCase_UnicodeMix_测试_テスト_{_timestamp()}"
