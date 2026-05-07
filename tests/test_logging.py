from src.logging_setup import redact_phi


def test_redacts_us_style_phone():
    out = redact_phi("Calling patient at 555-867-5309 now")
    assert "555-867-5309" not in out
    assert "REDACTED-PHONE" in out


def test_redacts_e164():
    out = redact_phi("phone=+14155552671")
    assert "4155552671" not in out
    assert "REDACTED-PHONE" in out


def test_redacts_parenthesized_format():
    out = redact_phi("contact (415) 555-2671 for follow-up")
    assert "555-2671" not in out
    assert "REDACTED-PHONE" in out


def test_does_not_mangle_short_numerics():
    # status codes, attempt counters, ports should pass through
    msg = "attempt 3 returned 503 on port 8000"
    assert redact_phi(msg) == msg


def test_does_not_redact_correlation_id_uuid_segments():
    cid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    msg = f"correlation_id={cid}"
    # UUID hex with dashes should not match the phone pattern (no leading digit)
    assert redact_phi(msg) == msg
