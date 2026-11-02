# ExamBit

A web-based online examination system with proctoring. Teachers create and publish exams.
Students take them in the browser under a server-controlled timer. The system grades
objective questions automatically, lets the teacher grade short answers, and watches each
attempt for rule violations.

## Features

- Registration and login for two roles, teacher and student, with hashed passwords
- Students belong to a course and admission session and see only the exams meant for them
- Exams with title, instructions, duration and an opening and closing time
- Question types: single choice, multiple correct, true/false, short answer
- Shuffled questions and options, a question palette, mark for review, automatic saving,
  a review page, and automatic submission when time runs out
- Proctoring: camera and entire-screen sharing, fullscreen, detection of tab or window
  switches, fullscreen exit, stopped screen sharing, camera off and right-clicks,
  a webcam snapshot every 30 seconds, and automatic submission at 10 violations
- Integrity score: 100 minus 10 for each violation
- Automatic grading of objective questions and manual grading of short answers
- Teacher results table, per-student proctoring report, and CSV export

## Tech stack

HTML, CSS and JavaScript on the front end. Python with Flask on the back end.
PostgreSQL with SQLAlchemy and Flask-Migrate. Flask-Login for sessions.

## Run it on your computer

1. Install Python 3.13 and PostgreSQL. Create a database named `exambit`.
2. In the project folder:

   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```

3. Edit `.env`:

   ```
   SECRET_KEY=any-long-random-text
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/exambit
   ```

4. Create the tables and start the app:

   ```
   flask --app run db upgrade
   python run.py
   ```

5. Open http://127.0.0.1:5000. Register a teacher account and a student account.

Camera and screen sharing work on `localhost` and on HTTPS sites. Use Chrome or Edge.

## Using it

1. As a teacher: create an exam, add questions, and publish it.
2. As a student: open the exam while its window is open, finish the system check, and begin.
3. As a teacher: open the exam, then "View attempts" to grade short answers, read the
   proctoring report, and download the results as CSV.

## Useful commands

- `flask --app run reset-data --snapshots-only` deletes webcam snapshots from your local database.
- `flask --app run reset-data --keep-users` deletes exams and attempts and keeps accounts.
- These commands refuse to run on a database that is not on your own computer.

## Limits

A browser can detect and record these actions. It cannot stop them. Proctoring here
deters misuse and leaves evidence for the teacher. It does not make cheating impossible.

