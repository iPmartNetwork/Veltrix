"""Unit tests for internationalization module."""
import pytest
from outpanel.i18n import t, get_language, set_language, get_translations, get_ui_labels, SUPPORTED_LANGUAGES


class TestI18n:
    def test_supported_languages(self):
        assert "fa" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES

    def test_translate_fa(self):
        result = t("server.name_required", lang="fa")
        assert "سرور" in result

    def test_translate_en(self):
        result = t("server.name_required", lang="en")
        assert "Server" in result

    def test_missing_key_returns_key(self):
        result = t("nonexistent.key")
        assert result == "nonexistent.key"

    def test_get_translations_returns_dict(self):
        translations = get_translations("en")
        assert isinstance(translations, dict)
        assert len(translations) > 0

    def test_get_ui_labels(self):
        labels = get_ui_labels("fa")
        assert "servers" in labels
        assert "logout" in labels

    def test_set_language(self):
        original = get_language()
        set_language("en")
        assert get_language() == "en"
        set_language(original)  # Restore
