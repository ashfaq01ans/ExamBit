
<div align="center">

# ExamBit

### Online Examination & Proctoring System

A web-based examination platform designed to simplify exam management, automate evaluation, and support examination integrity through browser-based proctoring.

[![Live Application](https://img.shields.io/badge/Live%20Application-Visit%20ExamBit-2563EB?style=for-the-badge)](https://exambit.onrender.com/login)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Source%20Code-181717?style=for-the-badge&logo=github)](https://github.com/ashfaq01ans/ExamBit)

</div>

---

## Overview

**ExamBit** is a web-based online examination and proctoring system that enables teachers to create, schedule, publish, and evaluate examinations while allowing students to take tests securely through a web browser.

The system combines examination management, server-controlled timing, automatic answer saving, objective evaluation, manual grading, and browser-based proctoring to provide an organised online examination experience.

It is developed using Python and Flask, with PostgreSQL as its database.

## Features

### 1. User Management

- Separate Teacher and Student roles.
- Secure user registration and login.
- Hashed password storage.
- Role-based access control.
- Student course and admission-session selection during registration.

### 2. Examination Management

- Create, edit, and delete examinations.
- Configure exam titles, instructions, duration, and availability.
- Schedule opening and closing times.
- Assign examinations to specific courses and admission sessions or make them available to everyone.
- Publish and unpublish examinations with confirmation.
- Lock examination settings once a student has started an attempt.
- Option to display correct answers after the examination window closes.
- Teacher dashboard organised into drafts, needs grading, live, upcoming, and past examinations.
- Course and month-based filters.

### 3. Question Management

Supports four question types:

- Single-choice questions
- Multiple-correct questions
- True/False questions
- Short-answer questions

Teachers can add, edit, delete, and change question types while managing examination content.

### 4. Student Examination Interface

- Students can access examinations assigned to their course and admission session.
- Pre-examination system check with consent, camera, entire-screen sharing, and fullscreen requirements.
- Server-controlled examination timer.
- Shuffled questions and answer options.
- Interactive question navigation palette.
- Mark questions for review.
- Automatic answer saving.
- Dedicated answer review page before submission.
- Automatic submission when the examination time expires.
- Result page displaying scores and examination details.
- Individual answer and marks review.

### 5. Online Proctoring

ExamBit includes browser-based monitoring features to record selected examination activities.

- Detects tab and window switching.
- Detects fullscreen exits.
- Detects stopped screen sharing.
- Detects camera interruptions.
- Detects right-clicks and developer-tools shortcuts.
- Blocks copy, cut, and paste actions.
- Captures webcam snapshots every 30 seconds.
- Records violations with timestamps.
- Maintains an examination integrity score.

**Integrity Scoring:**
- Initial integrity score: 100.
- Each recorded violation reduces the score by 10 points.
- Automatic examination submission after 10 violations.

Teachers can access individual attempt reports containing violation records, timestamps, integrity scores, webcam snapshots, and snapshot gaps. Snapshots can be deleted after grading.

### 6. Evaluation and Results

- Automatic evaluation of objective questions.
- Exact-match evaluation for multiple-correct questions.
- No negative marking.
- Manual evaluation of short-answer questions by teachers.
- Examination results table and score summaries.
- Graphical score representation.
- CSV export of examination results.

## Security Measures

Security is an important part of ExamBit's design.

- Passwords are stored using secure hashing.
- Sessions use signed cookies with HttpOnly, SameSite, and Secure settings over HTTPS.
- CSRF protection is applied to forms and background requests.
- Role-based access checks protect application pages and operations.
- Ownership checks ensure teachers access only their own examinations and students access only their own attempts.
- Examination timing, grading, and validation are handled on the server.
- Correct answers are not sent to the browser during an active examination.
- Webcam snapshot uploads are restricted to JPEG images with a maximum size of 1 MB.
- CSV export includes protection against spreadsheet formula injection.
- Security headers help prevent framing, content-type guessing, and unwanted page caching.
- HSTS is enabled over HTTPS.
- Sensitive configuration values are loaded through environment variables rather than hardcoded into the application.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript |
| Backend | Python 3.13 |
| Web Framework | Flask |
| Database | PostgreSQL |
| ORM | SQLAlchemy / Flask-SQLAlchemy |
| Database Migrations | Flask-Migrate |
| Authentication | Flask-Login |
| Application Server | Gunicorn |
| Database Hosting | Neon |
| Application Hosting | Render |
| Version Control | Git and GitHub |
| Development Environment | Visual Studio Code |

## Getting Started

Follow these instructions to run ExamBit locally.

### Prerequisites

Install the following before starting:

- Python 3.13
- PostgreSQL
- Git
- A modern web browser (Chrome or Edge recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/ashfaq01ans/ExamBit.git
```

Navigate to the project directory:

```bash
cd ExamBit
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a local PostgreSQL database named `exambit`.

Copy the example environment file:

```powershell
copy .env.example .env
```

Open `.env` and configure the required values:

```env
SECRET_KEY=your-long-random-secret-key
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/exambit
```

Replace the example database credentials with your own PostgreSQL details.

**Important:** Never commit your `.env` file or expose database credentials, secret keys, or other sensitive configuration values.

### 5. Apply Database Migrations

Create or update the database tables:

```bash
flask --app run db upgrade
```

### 6. Start the Application

```bash
python run.py
```

Open the application in your browser:

**http://127.0.0.1:5000**

You can now register a Teacher account and a Student account to explore the application.

> **Note:** Camera and screen-sharing features require a secure browser context. They work on localhost and HTTPS websites. Chrome and Edge are the primary supported browsers.

## How to Use

### Teacher Workflow

1. Register or log in using a Teacher account.
2. Create a new examination.
3. Configure examination details, duration, schedule, course, and admission session.
4. Add questions and their answer options.
5. Publish the examination.
6. View student attempts and examination results.
7. Evaluate short-answer responses manually.
8. Review proctoring reports and download result data as CSV.

### Student Workflow

1. Register or log in using a Student account.
2. Access examinations available for the assigned course and admission session.
3. Open an available examination.
4. Complete the pre-examination system check.
5. Give the required permissions for camera, screen sharing, and fullscreen.
6. Attempt questions within the allocated time.
7. Review answers and submit the examination.
8. View results and individual answer details when available.

## Deployment

ExamBit is deployed using **Render** for application hosting and **Neon** for PostgreSQL database hosting.

### Deployment Configuration

**1. Create a PostgreSQL Database**

- Create a database using Neon.
- Copy the PostgreSQL connection string.

**2. Apply Database Migrations**

In PowerShell, configure the Neon database URL temporarily:

```powershell
$env:DATABASE_URL = "YOUR_NEON_DATABASE_URL"
```

Apply the migrations:

```bash
flask --app run db upgrade
```

Remove the temporary environment variable:

```powershell
Remove-Item Env:DATABASE_URL
```

**3. Configure Render**

Create a new Render Web Service and connect the ExamBit GitHub repository.

Use the following configuration:

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn run:app` |

**4. Configure Environment Variables**

Add the following variables in the Render service settings:

```env
SECRET_KEY=your-production-secret-key
DATABASE_URL=your-neon-database-url
```

Deploy the application after saving the configuration.

### Database Migration Workflow

Whenever database models are modified, generate and apply migrations locally:

```bash
flask --app run db migrate
flask --app run db upgrade
```

Apply the migrations to the Neon database before deploying the updated application:

```powershell
$env:DATABASE_URL = "YOUR_NEON_DATABASE_URL"
flask --app run db upgrade
Remove-Item Env:DATABASE_URL
```

Then commit and push the updated code to GitHub.

## Useful Commands

### Application Commands

| Command | Purpose |
|---|---|
| `python run.py` | Start the Flask application |
| `pip install -r requirements.txt` | Install project dependencies |
| `flask --app run db upgrade` | Apply database migrations |
| `flask --app run db migrate` | Generate a database migration |

### Data Management Commands

**Delete webcam snapshots only:**

```bash
flask --app run reset-data --snapshots-only
```

**Delete examinations and attempts while retaining user accounts:**

```bash
flask --app run reset-data --keep-users
```

> **Warning:** These commands permanently delete selected data. They are restricted to databases recognised as being on your own computer. Use them carefully.

## Project Structure

```text
ExamBit/
│
├── app/
│   ├── __init__.py       # Application factory and error pages
│   ├── models.py         # Database models and relationships
│   ├── security.py       # CSRF protection and security headers
│   ├── grading.py        # Examination grading logic
│   ├── proctoring.py     # Proctoring rules and violation limits
│   ├── classes.py        # Courses and admission sessions
│   ├── timeutil.py       # Time zone handling (IST)
│   ├── cli.py            # Custom command-line operations
│   │
│   ├── auth/             # Authentication routes
│   ├── teacher/          # Teacher-related functionality
│   ├── student/          # Student-related functionality
│   ├── templates/        # HTML templates
│   └── static/           # CSS, JavaScript and static assets
│
├── migrations/           # Database migration files
├── config.py             # Application configuration
├── run.py                # Application entry point
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment configuration
└── README.md             # Project documentation
```

## Limitations

- Browser-based proctoring can detect and record selected activities, but it cannot prevent every form of misconduct.
- Proctoring depends on browser permissions for camera and screen sharing.
- Webcam snapshots may contain gaps if camera access or capture is interrupted.
- Free hosting services may temporarily sleep after periods of inactivity, resulting in slower initial page loads.
- Chrome and Edge are the primary supported browsers.

ExamBit is designed to support examination monitoring and provide teachers with recorded evidence of selected activities. It does not guarantee that cheating is impossible.

## Future Enhancements

Potential improvements include:

- AI-assisted proctoring and suspicious activity analysis.
- Face recognition and identity verification.
- Advanced examination analytics and performance tracking.
- Mobile application support.
- Expanded question bank management.
- Learning Management System (LMS) integration.
- Additional examination and reporting features.

---

## Project Information

| Detail | Description |
|---|---|
| Project Name | ExamBit |
| Project Type | Web-Based Online Examination and Proctoring System |
| Development Language | Python |
| Backend Framework | Flask |
| Database | PostgreSQL |
| Application Hosting | Render |
| Database Hosting | Neon |
| Repository | [GitHub - ExamBit](https://github.com/ashfaq01ans/ExamBit) |
| Live Application | [Open ExamBit](https://exambit.onrender.com/login) |

---

<div align="center">

**Developed as a Bachelor of Computer Applications (BCA) Semester Project.**

Copyright © 2026 ExamBit. All Rights Reserved.

Unauthorized copying, redistribution, or modification of this project without permission from the copyright holder is prohibited.

</div>
