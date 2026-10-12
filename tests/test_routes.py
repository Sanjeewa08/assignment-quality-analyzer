from io import BytesIO
from pathlib import Path

from sqlalchemy import inspect

from app import create_app, db
from app.models import Rubric, Submission, User


def test_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok"


def test_database_tables_are_created_when_app_starts(tmp_path, monkeypatch):
    monkeypatch.setenv("AQA_SECRET_KEY", "deployment-test-secret")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    assert app.config["SECRET_KEY"] == "deployment-test-secret"
    assert app.config["DEBUG"] is False
    with app.app_context():
        assert {"rubric", "submission", "user"} <= set(inspect(db.engine).get_table_names())


def test_legacy_ppt_is_hidden_and_rejected_without_libreoffice(client, app):
    app.config["LEGACY_PPT_AVAILABLE"] = False
    page = client.get("/")
    assert b".ppt," not in page.data
    assert b"Legacy .ppt files are disabled" in page.data

    response = client.post(
        "/analyze",
        data={"assignment": (BytesIO(b"presentation"), "legacy.ppt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"LibreOffice is not installed" in response.data


def test_anonymous_user_is_required_to_sign_in(client):
    with client.session_transaction() as session:
        session.clear()
    response = client.post("/analyze", data={})
    assert response.status_code == 302
    assert "/login" in response.location


def test_upload_route_returns_persisted_report_and_deletes_temp_upload(client, app):
    response = client.post(
        "/analyze",
        data={
            "assignment": (
                BytesIO(b"Introduction\nA useful assignment presents evidence. (Smith, 2024)\n\nAnalysis\nThe discussion is clear.\n\nConclusion\nThe conclusion summarizes the evidence."),
                "essay.txt",
            )
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"ANALYSIS REPORT" in response.data
    assert b"OVERALL QUALITY SCORE" in response.data
    with app.app_context():
        assert Submission.query.count() == 1
        assert list(Path(app.config["UPLOAD_FOLDER"]).iterdir()) == []


def test_empty_file_displays_friendly_error(client):
    response = client.post(
        "/analyze",
        data={"assignment": (BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"No readable text" in response.data


def test_missing_assignment_is_reported(client):
    response = client.post("/analyze", data={}, follow_redirects=True)
    assert b"Please choose a file" in response.data


def test_oversized_upload_is_rejected(client):
    response = client.post(
        "/analyze",
        data={"assignment": (BytesIO(b"x" * (10 * 1024 * 1024 + 1)), "large.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"exceeds the 10 MB limit" in response.data


def test_unsupported_upload_is_rejected(client):
    response = client.post(
        "/analyze",
        data={"assignment": (BytesIO(b"no"), "essay.exe")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"file type is not supported" in response.data


def test_invalid_word_requirement_is_reported(client):
    response = client.post(
        "/analyze",
        data={
            "min_words": "100",
            "max_words": "5",
            "assignment": (BytesIO(b"Introduction. Conclusion."), "essay.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"cannot exceed" in response.data


def test_register_login_logout_and_student_role_restriction(client, app):
    with client.session_transaction() as session:
        session.clear()
    response = client.post(
        "/register",
        data={"email": "new@example.test", "password": "very-secure-password"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Analyze assignment" in response.data
    with app.app_context():
        student = User.query.filter_by(email="new@example.test").one()
        assert student.role == "student"
    assert client.get("/rubrics").status_code == 403
    assert client.post("/logout").status_code == 302


def test_register_validates_fields_and_duplicate_email(client):
    with client.session_transaction() as session:
        session.clear()
    invalid_email = client.post(
        "/register",
        data={"email": "not-an-email", "password": "long-enough-password"},
        follow_redirects=True,
    )
    assert b"valid email" in invalid_email.data
    short_password = client.post(
        "/register",
        data={"email": "new@example.test", "password": "short"},
        follow_redirects=True,
    )
    assert b"at least 10 characters" in short_password.data
    duplicate = client.post(
        "/register",
        data={"email": "student@example.test", "password": "long-enough-password"},
        follow_redirects=True,
    )
    assert b"already exists" in duplicate.data


def test_login_rejects_bad_password_and_external_redirect(client):
    with client.session_transaction() as session:
        session.clear()
    rejected = client.post(
        "/login",
        data={"email": "student@example.test", "password": "wrong-password"},
        follow_redirects=True,
    )
    assert b"not recognized" in rejected.data
    with client.session_transaction() as session:
        session.clear()
    logged_in = client.post(
        "/login?next=https://evil.example",
        data={"email": "student@example.test", "password": "secure-test-password"},
        follow_redirects=False,
    )
    assert logged_in.status_code == 302
    assert logged_in.location == "/"


def test_login_requires_an_account(client):
    with client.session_transaction() as session:
        session.clear()
    response = client.get("/history")
    assert response.status_code == 302
    assert "/login" in response.location


def test_student_cannot_access_other_users_submission(client, app):
    with app.app_context():
        other = User(email="other@example.test", password_hash=User.hash_password("secure-test-password"), role="student")
        db.session.add(other)
        db.session.flush()
        record = Submission(
            user_id=other.id,
            file_name="private.txt",
            extracted_text="private text",
            report_json="{}",
            word_count=2,
            quality_score=50,
        )
        db.session.add(record)
        db.session.commit()
        submission_id = record.id
    assert client.get(f"/report/{submission_id}").status_code == 404


def test_lecturer_can_create_rubric_and_student_can_select_it(client, app):
    with app.app_context():
        lecturer = User(email="lecturer@example.test", password_hash=User.hash_password("secure-test-password"), role="lecturer")
        db.session.add(lecturer)
        db.session.commit()
        lecturer_id = lecturer.id
    with client.session_transaction() as session:
        session["_user_id"] = str(lecturer_id)
        session["_fresh"] = True
    response = client.post(
        "/rubrics",
        data={"title": "Essay basics", "criteria": "Must include a conclusion\nMin 10 words"},
        follow_redirects=True,
    )
    assert b"Essay basics" in response.data
    with app.app_context():
        rubric = Rubric.query.filter_by(title="Essay basics").one()
        rubric_id = rubric.id
        student_id = User.query.filter_by(email="student@example.test").one().id
    with client.session_transaction() as session:
        session["_user_id"] = str(student_id)
        session["_fresh"] = True
    response = client.post(
        "/analyze",
        data={
            "rubric_id": str(rubric_id),
            "assignment": (BytesIO(b"Introduction\nA sentence.\nConclusion\nClosing."), "rubric.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Rubric checklist" in response.data


def test_report_pdf_export(client, app, monkeypatch):
    response = client.post(
        "/analyze",
        data={"assignment": (BytesIO(b"Introduction. Analysis. Conclusion."), "essay.txt")},
        content_type="multipart/form-data",
    )
    with app.app_context():
        record = Submission.query.one()
        submission_id = record.id
    pdf = client.get(f"/report/{submission_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")


def test_rubric_invalid_and_empty_rules_are_rejected(client, app):
    with app.app_context():
        lecturer = User(email="rubric@example.test", password_hash=User.hash_password("secure-test-password"), role="lecturer")
        db.session.add(lecturer)
        db.session.commit()
        lecturer_id = lecturer.id
    with client.session_transaction() as session:
        session["_user_id"] = str(lecturer_id)
        session["_fresh"] = True
    missing_title = client.post(
        "/rubrics",
        data={"title": "", "criteria": "Must include a conclusion"},
        follow_redirects=True,
    )
    assert b"Enter a rubric title" in missing_title.data
    missing_rules = client.post(
        "/rubrics",
        data={"title": "Empty rubric", "criteria": ""},
        follow_redirects=True,
    )
    assert b"Add at least one criterion" in missing_rules.data


def test_report_not_found_and_invalid_rubric_selection(client):
    assert client.get("/report/9999").status_code == 404
    response = client.post(
        "/analyze",
        data={"rubric_id": "9999", "assignment": (BytesIO(b"essay"), "essay.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"selected rubric could not be found" in response.data


def test_progress_history_displays_previous_submission(client, app):
    client.post(
        "/analyze",
        data={"assignment": (BytesIO(b"Introduction. Analysis. Conclusion."), "essay.txt")},
        content_type="multipart/form-data",
    )
    response = client.get("/history")
    assert response.status_code == 200
    assert b"essay.txt" in response.data
    assert b"progress-chart" in response.data


def test_database_and_lecturer_cli_commands(app):
    runner = app.test_cli_runner()
    initialized = runner.invoke(args=["init-db"])
    assert initialized.exit_code == 0
    created = runner.invoke(
        args=["create-lecturer"],
        input="cli-lecturer@example.test\ncli-secure-password\ncli-secure-password\n",
    )
    assert created.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="cli-lecturer@example.test", role="lecturer").one()
