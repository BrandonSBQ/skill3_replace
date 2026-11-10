from risk_news_v2.console_text import console_safe


def test_console_safe_replaces_unencodable_legal_name_for_gbk_stream():
    value = console_safe("A.P. Møller - Mærsk A/S", encoding="gbk")
    value.encode("gbk")
    assert "M" in value and "A/S" in value
    assert "\\xf8" in value


def test_console_safe_preserves_unicode_for_utf8_stream():
    value = "A.P. Møller - Mærsk A/S"
    assert console_safe(value, encoding="utf-8") == value

