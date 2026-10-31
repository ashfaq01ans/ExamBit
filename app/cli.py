import click
from flask import current_app
from sqlalchemy.engine import make_url

from app import db
from app.models import Answer, Attempt, Exam, Option, Question, Snapshot, User, Violation

LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}


@click.command("reset-data")
@click.option("--keep-users", is_flag=True, help="Keep user accounts and delete everything else.")
@click.option("--snapshots-only", is_flag=True, help="Delete only the webcam snapshots.")
def reset_data(keep_users, snapshots_only):
    """Delete local test data. Refuses to run on a remote database."""
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if url.host not in LOCAL_HOSTS:
        raise click.ClickException(
            f"Refusing to run: the database host is '{url.host}', not this computer."
        )

    if snapshots_only:
        message = "Delete ALL webcam snapshots in the local database?"
    elif keep_users:
        message = "Delete ALL exams, attempts and snapshots (users are kept)?"
    else:
        message = "Delete ALL data, including user accounts?"
    if not click.confirm(message):
        click.echo("Cancelled.")
        return

    db.session.execute(db.delete(Snapshot))
    if not snapshots_only:
        # children first, so no foreign key is broken
        for model in (Violation, Answer, Attempt, Option, Question, Exam):
            db.session.execute(db.delete(model))
        if not keep_users:
            db.session.execute(db.delete(User))
    db.session.commit()
    click.echo("Done.")
