"""Internationalization (i18n) for Veltrix.

Supports Persian (fa) and English (en) with runtime language switching.
Translations are used in API error messages and notification texts.
"""
from __future__ import annotations

import os
from typing import Any


# Current language (default from env or 'fa')
_current_lang: str = os.getenv("OUTPANEL_LANGUAGE", "fa").strip().lower()

SUPPORTED_LANGUAGES = {
    "fa": "فارسی",
    "en": "English",
}

# ---------------------------------------------------------------------------
# Translation dictionaries
# ---------------------------------------------------------------------------

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # Auth
    "auth.owner_exists": {
        "fa": "حساب ادمین اصلی قبلاً ساخته شده است.",
        "en": "The main owner account has already been created.",
    },
    "auth.incorrect_credentials": {
        "fa": "نام کاربری یا رمز عبور اشتباه است.",
        "en": "Incorrect username or password.",
    },
    "auth.rate_limited": {
        "fa": "تعداد تلاش‌های ناموفق زیاد است. لطفاً بعداً تلاش کنید.",
        "en": "Too many failed attempts. Please try again later.",
    },
    "auth.password_same": {
        "fa": "رمز جدید باید با رمز فعلی متفاوت باشد.",
        "en": "The new password must be different from the current one.",
    },
    "auth.password_wrong": {
        "fa": "رمز فعلی اشتباه است.",
        "en": "The current password is incorrect.",
    },
    "auth.password_short": {
        "fa": "رمز عبور باید حداقل ۸ کاراکتر باشد.",
        "en": "Password must be at least 8 characters.",
    },
    "auth.username_required": {
        "fa": "نام کاربری الزامی است.",
        "en": "Username is required.",
    },
    "auth.username_invalid": {
        "fa": "نام کاربری باید ۳ تا ۴۰ کاراکتر شامل حروف، اعداد، خط تیره یا نقطه باشد.",
        "en": "Username must be 3-40 characters: letters, digits, underscore, dot, or dash.",
    },
    "auth.manager_limit": {
        "fa": "حداکثر تعداد مدیرها پر شده است.",
        "en": "Maximum number of managers reached.",
    },
    "auth.username_taken": {
        "fa": "این نام کاربری قبلاً استفاده شده است.",
        "en": "This username is already taken.",
    },
    "auth.no_permission": {
        "fa": "شما دسترسی لازم برای این عملیات را ندارید.",
        "en": "You do not have permission to access this resource.",
    },

    # Server
    "server.name_required": {
        "fa": "نام سرور الزامی است.",
        "en": "Server name is required.",
    },
    "server.host_required": {
        "fa": "آدرس IP یا دامنه سرور الزامی است.",
        "en": "Server host is required.",
    },
    "server.not_found": {
        "fa": "سرور یافت نشد.",
        "en": "Server not found.",
    },
    "server.limit_reached": {
        "fa": "سقف تعداد سرورها پر شده. برای افزودن سرور بیشتر لایسنس را ارتقا دهید.",
        "en": "Server limit reached. Upgrade your license to add more servers.",
    },

    # Outbound
    "outbound.not_found": {
        "fa": "اوت‌باند یافت نشد.",
        "en": "Outbound not found.",
    },
    "outbound.auto_disabled": {
        "fa": "اوت‌باند به دلیل خرابی مکرر غیرفعال شد.",
        "en": "Outbound was auto-disabled due to repeated failures.",
    },

    # License
    "license.key_empty": {
        "fa": "کلید لایسنس خالی است.",
        "en": "License key is empty.",
    },
    "license.server_not_configured": {
        "fa": "آدرس سرور لایسنس تنظیم نشده است.",
        "en": "License server URL is not configured.",
    },
    "license.required": {
        "fa": "لایسنس معتبر برای این عملیات لازم است.",
        "en": "A valid license is required.",
    },

    # Backup
    "backup.db_not_found": {
        "fa": "فایل دیتابیس یافت نشد.",
        "en": "Database file was not found.",
    },
    "backup.invalid_name": {
        "fa": "نام بکاپ نامعتبر است.",
        "en": "Backup name is invalid.",
    },
    "backup.not_found": {
        "fa": "فایل بکاپ یافت نشد.",
        "en": "Backup file was not found.",
    },

    # Notification
    "notification.not_found": {
        "fa": "کانال اعلان یافت نشد.",
        "en": "Notification channel not found.",
    },
    "notification.type_invalid": {
        "fa": "نوع کانال اعلان باید telegram یا webhook باشد.",
        "en": "Channel type must be telegram or webhook.",
    },
    "notification.telegram_required": {
        "fa": "Bot Token و Chat ID تلگرام الزامی است.",
        "en": "Telegram bot_token and chat_id are required.",
    },
    "notification.webhook_required": {
        "fa": "آدرس Webhook الزامی است.",
        "en": "Webhook URL is required.",
    },

    # General
    "general.invalid_json": {
        "fa": "فرمت JSON نامعتبر است.",
        "en": "Invalid JSON.",
    },
    "general.unauthorized": {
        "fa": "دسترسی رد شد.",
        "en": "Unauthorized.",
    },
    "general.not_found": {
        "fa": "یافت نشد.",
        "en": "Not found.",
    },
    "general.rate_limited": {
        "fa": "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید.",
        "en": "Too many requests. Please slow down.",
    },

    # Reports
    "report.weekly_title": {
        "fa": "📊 گزارش هفتگی Veltrix",
        "en": "📊 Veltrix Weekly Report",
    },

    # UI labels (used in frontend via API)
    "ui.servers": {"fa": "سرورها", "en": "Servers"},
    "ui.outbounds": {"fa": "اوت‌باندها", "en": "Outbounds"},
    "ui.alerts": {"fa": "اعلان‌ها", "en": "Alerts"},
    "ui.incidents": {"fa": "رخدادها", "en": "Incidents"},
    "ui.license": {"fa": "لایسنس", "en": "License"},
    "ui.backup": {"fa": "بکاپ", "en": "Backup"},
    "ui.settings": {"fa": "تنظیمات", "en": "Settings"},
    "ui.logout": {"fa": "خروج", "en": "Logout"},
    "ui.login": {"fa": "ورود", "en": "Login"},
    "ui.save": {"fa": "ذخیره", "en": "Save"},
    "ui.delete": {"fa": "حذف", "en": "Delete"},
    "ui.cancel": {"fa": "انصراف", "en": "Cancel"},
    "ui.edit": {"fa": "ویرایش", "en": "Edit"},
    "ui.refresh": {"fa": "بروزرسانی", "en": "Refresh"},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_language() -> str:
    """Get the current language code."""
    return _current_lang


def set_language(lang: str) -> None:
    """Set the current language."""
    global _current_lang
    if lang in SUPPORTED_LANGUAGES:
        _current_lang = lang


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Translate a key to the current (or specified) language.

    Supports format placeholders: t("server.limit", max=20)
    """
    target_lang = lang or _current_lang
    entry = _TRANSLATIONS.get(key)
    if not entry:
        return key

    text = entry.get(target_lang) or entry.get("fa") or entry.get("en") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_translations(lang: str | None = None) -> dict[str, str]:
    """Get all translations for a language (for frontend use)."""
    target_lang = lang or _current_lang
    result = {}
    for key, entry in _TRANSLATIONS.items():
        result[key] = entry.get(target_lang) or entry.get("fa") or key
    return result


def get_ui_labels(lang: str | None = None) -> dict[str, str]:
    """Get UI label translations for the frontend."""
    target_lang = lang or _current_lang
    result = {}
    for key, entry in _TRANSLATIONS.items():
        if key.startswith("ui."):
            short_key = key[3:]
            result[short_key] = entry.get(target_lang) or entry.get("fa") or short_key
    return result
