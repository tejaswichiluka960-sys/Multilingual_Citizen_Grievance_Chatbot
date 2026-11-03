# Citizen registration and login

The citizen web flow is now language-first:

1. `/welcome` asks the citizen to choose English, Hindi or Telugu.
2. The selected language opens the localized registration page.
3. Registration stores the username, PBKDF2 password hash and preferred language.
4. The citizen is logged in automatically and redirected to the localized chat page.
5. Future login uses the same language saved in the citizen account.
6. A database-backed, HTTP-only session cookie protects the chat page.
7. `/logout` clears the browser session.

Existing Telegram users remain valid. Their records can have no web username because Telegram authentication is separate. Existing tickets and departments are preserved when the authentication schema is initialized.
