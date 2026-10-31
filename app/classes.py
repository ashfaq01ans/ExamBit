from datetime import datetime

# Courses offered. Add or remove names here.
COURSES = ["BCA", "BBA", "BA", "MCA", "MBA"]

# The university admits students twice a year.
INTAKE_MONTHS = ("Jul", "Jan")


def session_options():
    """Admission sessions, newest first: 'Jul 2026', 'Jan 2026', 'Jul 2025', ... (5 years)."""
    year = datetime.now().year
    return [f"{month} {y}" for y in range(year, year - 5, -1) for month in INTAKE_MONTHS]
