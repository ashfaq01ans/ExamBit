# ExamBit notes
Stack: Python 3.13, Flask, PostgreSQL 18, SQLAlchemy, Flask-Login, Flask-Migrate
DB URL prefix must be postgresql+psycopg2:// (not postgresql://)
Project lives in C:\dev\exambit (never in OneDrive)
Done: setup, 8 models + migrations, auth (register, login, logout, roles), password toggle
Next: teacher exam and question creation
Later: attempt engine, proctoring, grading, reports, styling, deploy (Render + Neon)

TODO later
- Edit existing question
- CSRF protection (Flask-WTF)
- Toast messages (flash to JavaScript toasts, error toasts stay)
- Centered confirm popup (replaces browser confirm)
- Login success flash message
- Styling (custom CSS, no Tailwind)
- Take report screenshots after styling
- Deploy: Render + Neon, run db upgrade on Neon

limitiaions to know 
A browser can detect and log these actions. It cannot stop them. A determined cheater can use a second phone. Proctoring here deters and leaves evidence.
Chrome and Edge are the supported browsers. Firefox and Safari may not report what was shared, so any share is accepted.
A covered camera lens is not detected. “Camera off” fires only when the device is removed or permission is revoked.
An OS notification popup can steal focus and count as a tab switch. Tell students to close other apps.