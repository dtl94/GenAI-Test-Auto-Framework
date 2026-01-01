LOGIN_STEPS = [
    (r"navigate to login page", "page.goto(config['pages']['login']['url'])"),
    (r"enter valid username", "login.enter_username(config['credentials']['valid']['username'])"),
    (r"enter valid password", "login.enter_password(config['credentials']['valid']['password'])"),
    (r"enter invalid password", "login.enter_password(config['credentials']['invalid']['password'])"),
    (r"click login button", "login.click_login()"),
]
