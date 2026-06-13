"""Authentication scenarios: positive + negative + session (TC-001/007/008/009).

This module is named ``test_00_...`` so pytest collects it **before** other
``tests/test_*.py`` files — TC-001 valid login runs first without collection hooks.
"""
from __future__ import annotations

import allure
import pytest

from config.config import settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage


@allure.epic("TestRail UI")
@allure.feature("Authentication")
class TestLogin:

    @allure.story("TC-001 Positive: valid login")
    @pytest.mark.positive
    @pytest.mark.smoke
    def test_00_tc001_valid_login(self, driver, login_page: LoginPage):
        login_page.open_login()
        login_page.login_expecting_success(settings.email, settings.password)

        dashboard = DashboardPage(driver)
        assert "/auth/login" not in login_page.current_url(), "URL must change away from login page"
        assert dashboard.is_dashboard_displayed(), "App shell must load after login (dashboard, onboarding, or similar)"
        assert dashboard.is_user_logged_in(), "User menu / logout must be visible after login"

    @allure.story("TC-007 Negative: invalid password")
    @pytest.mark.negative
    def test_invalid_password(self, login_page: LoginPage):
        login_page.open_login()
        login_page.login(settings.email, "DefinitelyWrongPassword_123!")
        login_page.expect_failed_login()
        assert login_page.is_on_login_page(), "User must remain on the login page"

    @allure.story("TC-007b Negative: fully invalid credentials")
    @pytest.mark.negative
    def test_invalid_login(self, login_page: LoginPage):
        login_page.open_login()
        login_page.login("not-a-real-user@example.com", "WrongPassword123!")
        login_page.expect_failed_login()
        assert login_page.is_on_login_page(), "User must remain on the login page"

    @allure.story("TC-008 Negative: empty credentials (both fields empty)")
    @pytest.mark.negative
    def test_empty_credentials(self, login_page: LoginPage):
        login_page.open_login()
        login_page.login("", "")
        assert login_page.is_on_login_page(), "Login must be rejected when both fields are empty"

    @allure.story("TC-008a Negative: empty email")
    @pytest.mark.negative
    def test_empty_login(self, login_page: LoginPage):
        login_page.open_login()
        login_page.login("", settings.password)
        assert login_page.is_on_login_page(), "Login must be rejected when email is empty"

    @allure.story("TC-008b Negative: empty password")
    @pytest.mark.negative
    def test_empty_password(self, login_page: LoginPage):
        login_page.open_login()
        login_page.login(settings.email, "")
        assert login_page.is_on_login_page(), "User must remain on the login page when password is empty"

    @allure.story("TC-009 Session persistence after refresh")
    @pytest.mark.positive
    def test_session_persistence_after_refresh(self, driver, logged_in: DashboardPage):
        assert logged_in.is_user_logged_in(), "Precondition: user must be logged in"
        logged_in.refresh()
        assert "/auth/login" not in driver.current_url, "Refresh must not log the user out"
        assert logged_in.is_user_logged_in(), "User must remain logged in after a page refresh"
