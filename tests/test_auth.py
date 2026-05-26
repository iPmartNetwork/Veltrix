"""Unit tests for authentication module."""
import pytest
from outpanel.auth import (
    hash_password,
    verify_password,
    normalize_username,
    normalize_display_name,
    validate_password,
    validate_manager_permissions,
    parse_permissions,
    has_permission,
    all_permissions,
    manager_permissions,
    ROLE_OWNER,
    ROLE_MANAGER,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("secure_password_123")
        assert verify_password("secure_password_123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_empty_password_fails(self):
        hashed = hash_password("something")
        assert not verify_password("", hashed)

    def test_hash_format(self):
        hashed = hash_password("test")
        assert hashed.startswith("pbkdf2:sha256:")
        assert "$" in hashed

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # Different salts

    def test_verify_with_empty_hash(self):
        assert not verify_password("test", "")
        assert not verify_password("test", None)


class TestUsernameValidation:
    def test_valid_username(self):
        assert normalize_username("admin") == "admin"
        assert normalize_username("user_01") == "user_01"
        assert normalize_username("test.user") == "test.user"
        assert normalize_username("my-name") == "my-name"

    def test_username_lowercased(self):
        assert normalize_username("Admin") == "admin"
        assert normalize_username("USER") == "user"

    def test_username_stripped(self):
        assert normalize_username("  admin  ") == "admin"

    def test_empty_username_raises(self):
        with pytest.raises(ValueError):
            normalize_username("")
        with pytest.raises(ValueError):
            normalize_username(None)

    def test_short_username_raises(self):
        with pytest.raises(ValueError):
            normalize_username("ab")

    def test_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            normalize_username("user name")
        with pytest.raises(ValueError):
            normalize_username("user@name")


class TestDisplayNameValidation:
    def test_valid_name(self):
        assert normalize_display_name("Admin User") == "Admin User"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_display_name("")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            normalize_display_name("x" * 81)


class TestPasswordValidation:
    def test_valid_password(self):
        assert validate_password("12345678") == "12345678"

    def test_short_password_raises(self):
        with pytest.raises(ValueError):
            validate_password("1234567")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            validate_password("x" * 129)


class TestPermissions:
    def test_owner_has_all_permissions(self):
        user = {"role": ROLE_OWNER}
        assert has_permission(user, "servers")
        assert has_permission(user, "license")
        assert has_permission(user, "users")

    def test_manager_with_permission(self):
        user = {"role": ROLE_MANAGER, "permissions": ["servers", "outbounds"]}
        assert has_permission(user, "servers")
        assert has_permission(user, "outbounds")
        assert not has_permission(user, "license")

    def test_none_user_no_permission(self):
        assert not has_permission(None, "servers")

    def test_parse_permissions_from_json(self):
        user = {"permissions_json": '["servers", "outbounds"]'}
        assert parse_permissions(user) == ["servers", "outbounds"]

    def test_parse_permissions_invalid_json(self):
        user = {"permissions_json": "invalid"}
        assert parse_permissions(user) == []

    def test_validate_manager_permissions(self):
        result = validate_manager_permissions(["servers", "outbounds", "invalid_perm"])
        assert "servers" in result
        assert "outbounds" in result
        assert "invalid_perm" not in result

    def test_all_permissions_includes_users(self):
        assert "users" in all_permissions()

    def test_manager_permissions_excludes_users(self):
        assert "users" not in manager_permissions()
