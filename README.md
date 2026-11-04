# ExamBit

A web-based online examination system with proctoring. Teachers create and publish exams.
Students take them in the browser under a server-controlled timer. The system grades
objective questions automatically, lets the teacher grade short answers, and watches each
attempt for rule violations.

## Features

**Accounts**
- Teacher and student roles, with hashed passwords
- Students choose their course and admission session when they register

**Exams and questions (teacher)**
- Create, edit and delete exams: title, instructions, duration, opening and closing time
- Each exam is for one course and session, or open to everyone
- Question types: single choice, multiple correct, true/false, short answer
- Add, edit and delete questions, and switch a question's type
- Publish and unpublish with a confirmation. An exam locks once a student has started it
- Option to show correct answers to students after the exam window closes
- Dashboard grouped into drafts, needs grading, live and upcoming, and past exams,
  with course and month filters

**Taking an exam (student)**
- Students see only the exams for their own course and session
- System check before the exam: consent, camera, entire-screen sharing, fullscreen
- The timer runs on the server, so refreshing or closing the page cannot add time
- Shuffled questions and options, a question palette, mark for review, automatic saving,
  a review page, and automatic submission when time runs out
- Result page and a page with the student's own answers and marks

**Proctoring**
- Detects tab or window switches, leaving fullscreen, stopped screen sharing, camera off,
  right-clicks, and developer-tools shortcuts. Copy, cut and paste are blocked
- A webcam snapshot every 30 seconds
- Integrity score: 100, minus 10 for each violation. At 10 violations the exam is submitted automatically
- Teacher report per attempt: violations with times, integrity score, snapshots,
  and gaps in the snapshots. Snapshots can be deleted after grading

**Grading and results**
- Objective questions are graded automatically. Multiple-correct questions need an exact match.
  There is no negative marking
- Short answers are graded by the teacher
- Results table, score summary with a chart, and CSV export

## Security

- Passwords are hashed. Sessions use signed cookies (HttpOnly, SameSite, and Secure over HTTPS)
- CSRF tokens on every form and background request
- Role checks on every page, and ownership checks so teachers see only their own exams and
  students see only their own attempts
- The timer, grading and all checks run on the server. Correct answers are never sent to the browser
- Uploads are limited to 1 MB and must be JPEG images. CSV export guards against spreadsheet formulas
- Security headers: no framing, no content-type guessing, HSTS on HTTPS, no caching of pages
- Secrets are read from environment variables, never stored in the code

## Tech stack

HTML, CSS and JavaScript on the front end (no framework). Python 3.13 with Flask on the back end.
PostgreSQL with SQLAlchemy and Flask-Migrate. Flask-Login for sessions.
Hosted on Render, with the database on Neon.

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

5. Open http://127.0.0.1:5000. Register a teacher and a student.

Camera and screen sharing work on `localhost` and on HTTPS sites. Use Chrome or Edge.

## Using it

1. Teacher: create an exam, add questions, and publish it.
2. Student: open the exam while its window is open, finish the system check, and begin.
3. Teacher: open the exam's results to grade short answers, read the proctoring reports,
   see the score summary, and download the CSV.

## Deploying

1. Create a PostgreSQL database on Neon and copy its connection string.
2. From your computer, create the tables on it:

   ```
   $env:DATABASE_URL = "the Neon connection string"
   flask --app run db upgrade
   Remove-Item Env:DATABASE_URL
   ```

3. Create a Render web service from the GitHub repository.
   Build command: `pip install -r requirements.txt`. Start command: `gunicorn run:app`.
4. Set the environment variables `SECRET_KEY` and `DATABASE_URL` on Render.

After changing a database model, run `flask --app run db migrate` and `db upgrade` locally,
then `db upgrade` against Neon, and then push the code.

## Project layout

```
app/
  __init__.py     app factory, error pages
  models.py       database tables
  security.py     CSRF protection and response headers
  grading.py      marking rules
  proctoring.py   violation types and limits
  classes.py      courses and admission sessions
  timeutil.py     time zone handling (IST)
  cli.py          the reset-data command
  auth/ teacher/ student/   routes for each part
  templates/ static/
migrations/       database migrations
config.py         settings read from the environment
run.py            entry point
```

## Useful commands

- `flask --app run reset-data --snapshots-only` deletes webcam snapshots from your local database
- `flask --app run reset-data --keep-users` deletes exams and attempts and keeps accounts
- These commands refuse to run on a database that is not on your own computer

## Limits

A browser can detect and report these actions. It cannot stop them. Proctoring here deters
misuse and leaves evidence for the teacher, including gaps in the snapshots. It does not
make cheating impossible. Free hosting sleeps after a period of no use, so the first page
load can be slow.
