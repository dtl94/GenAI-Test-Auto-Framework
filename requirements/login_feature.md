Feature: Login

Page: login

Scenarios:

- Valid login
  Steps:
    - Navigate to login page
    - Enter valid username
    - Enter valid password
    - Click login button
  Expected:
    - User is redirected to inventory page

- Invalid password
  Steps:
    - Navigate to login page
    - Enter valid username
    - Enter invalid password
    - Click login button
  Expected:
    - Error message is shown
