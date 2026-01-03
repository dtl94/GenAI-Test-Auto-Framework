from playwright.sync_api import Page

class LoginPage:
    def __init__(self, page: Page):
        self.page = page

        self._username_input_field = 'data-test=username'
        self._password_input_field = 'data-test=password'
        self._login_button = 'data-test=login-button'
        self._error_message = 'div.error-message-container'

    def enter_username_input_field(self, value):
        self.page.fill(self._username_input_field, value)

    def enter_password_input_field(self, value):
        self.page.fill(self._password_input_field, value)

    def click_login_button(self):
        self.page.click(self._login_button)

    def get_error_message_text(self):
        return self.page.locator(self._error_message).text_content()
