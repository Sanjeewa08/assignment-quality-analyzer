import json
import logging
import tempfile
from datetime import timezone
from io import BytesIO
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_file
from flask_login import current_user, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.utils import secure_filename

from . import db
from .analyzers.rubric import parse_rubric
from .extractors import ExtractionError, extract_document
from .models import Rubric, Submission, User
from .services.analysis import analyze_assignment

logger = logging.getLogger(__name__)
api = Blueprint("api", __name__, url_prefix="/api")


def _require_user():
    if not current_user.is_authenticated:
        return jsonify(error="Please sign in to continue."), 401
    return None


def _user_json(user):
    return {"id": user.id, "email": user.email, "role": user.role}


def _date_json(value):
    return value.replace(tzinfo=timezone.utc).isoformat()


def _submission_json(submission, include_report=False):
    result = {
        "id": submission.id,
        "file_name": submission.file_name,
        "word_count": submission.word_count,
        "quality_score": submission.quality_score,
        "created_at": _date_json(submission.created_at),
    }
    if include_report:
        result["report"] = json.loads(submission.report_json)
    return result


@api.get("/csrf")
def csrf_token():
    return jsonify(csrf_token=generate_csrf())


@api.get("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify(user=None)
    return jsonify(user=_user_json(current_user))


@api.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not email or "@" not in email or len(email) > 255:
        return jsonify(error="Enter a valid email address."), 400
    if not isinstance(password, str) or len(password) < 10:
        return jsonify(error="Use a password with at least 10 characters."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="An account with that email already exists."), 409
    user = User(email=email, password_hash=User.hash_password(password), role="student")
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify(user=_user_json(user)), 201


@api.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data.get("password", "") if isinstance(data.get("password", ""), str) else ""):
        return jsonify(error="Email or password was not recognized."), 401
    login_user(user, remember=bool(data.get("remember")))
    return jsonify(user=_user_json(user))


@api.post("/auth/logout")
def logout():
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    logout_user()
    return jsonify(ok=True)


@api.get("/rubrics")
def list_rubrics():
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    rows = Rubric.query.order_by(Rubric.title.asc()).all()
    return jsonify(rubrics=[{"id": row.id, "title": row.title} for row in rows])


@api.post("/rubrics")
def create_rubric():
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    if current_user.role != "lecturer":
        return jsonify(error="Lecturer access is required."), 403
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    criteria_text = data.get("criteria", "")
    if not isinstance(criteria_text, str):
        return jsonify(error="Criteria must be text, one criterion per line."), 400
    criteria = parse_rubric(criteria_text)
    if not title or len(title) > 120:
        return jsonify(error="Enter a rubric title up to 120 characters."), 400
    if not criteria:
        return jsonify(error="Add at least one criterion, one per line."), 400
    row = Rubric(
        author_id=current_user.id,
        title=title,
        criteria_json=json.dumps(criteria),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(rubric={"id": row.id, "title": row.title}), 201


@api.post("/analyze")
def analyze():
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    uploaded = request.files.get("assignment")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="Please choose a file to analyze."), 400
    safe_name = secure_filename(uploaded.filename)
    if not safe_name:
        return jsonify(error="The filename is invalid. Rename the file and try again."), 400
    extension = Path(safe_name).suffix.lower()
    if extension == ".ppt" and not current_app.config["LEGACY_PPT_AVAILABLE"]:
        return jsonify(error="Legacy .ppt files are unavailable because LibreOffice is not installed. Please save as .pptx."), 400
    if extension not in current_app.extensions["extractor_extensions"]:
        return jsonify(error="This file type is not supported. Upload TXT, DOCX, PDF, PPT, PPTX, JPG, JPEG, or PNG."), 400

    temporary_path = None
    try:
        def form_int(key):
            raw = request.form.get(key, "").strip()
            if not raw:
                return None
            try:
                value = int(raw)
            except ValueError as exc:
                raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a whole number.") from exc
            if value < 1:
                raise ValueError(f"{key.replace('_', ' ').capitalize()} must be greater than zero.")
            return value

        minimum = form_int("min_words")
        maximum = form_int("max_words")
        min_references = form_int("min_references")
        if minimum and maximum and minimum > maximum:
            raise ValueError("Minimum word count cannot exceed maximum word count.")
        rubric_id = request.form.get("rubric_id", "").strip()
        rubric = db.session.get(Rubric, int(rubric_id)) if rubric_id.isdigit() else None
        if rubric_id and rubric is None:
            raise ValueError("The selected rubric could not be found.")

        upload_dir = current_app.config["UPLOAD_FOLDER"]
        handle = tempfile.NamedTemporaryFile(
            prefix="assignment-",
            suffix=extension,
            dir=upload_dir,
            delete=False,
        )
        temporary_path = Path(handle.name)
        handle.close()
        uploaded.save(temporary_path)
        document = extract_document(temporary_path)
        if not document.text.strip():
            raise ExtractionError("No readable text was found in this file. Scanned files require working OCR tools.")
        if len(document.text) > 1_000_000:
            raise ExtractionError("The extracted document is unusually large. Split it into smaller files and try again.")
        prior = (
            Submission.query.filter(Submission.extracted_text != "")
            .order_by(Submission.created_at.desc())
            .limit(25)
            .all()
        )
        comparisons = [("another local submission", item.extracted_text[:100_000]) for item in prior]
        criteria = json.loads(rubric.criteria_json) if rubric else []
        report = analyze_assignment(
            document.text,
            formatting=document.formatting,
            min_words=minimum,
            max_words=maximum,
            other_submissions=comparisons,
            reference_text=request.form.get("reference_text", ""),
            rubric_criteria=criteria,
            min_references=min_references,
        )
        submission = Submission(
            user_id=current_user.id,
            file_name=safe_name,
            extracted_text=document.text,
            report_json=json.dumps(report, ensure_ascii=False),
            word_count=report["writing"]["counts"]["words"],
            quality_score=report["overall_score"],
        )
        db.session.add(submission)
        db.session.commit()
        return jsonify(submission=_submission_json(submission, include_report=True)), 201
    except (ExtractionError, ValueError) as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400
    except Exception:
        db.session.rollback()
        logger.exception("Assignment API analysis failed for user %s", current_user.get_id())
        return jsonify(error="We could not analyze this file. Check that it is valid and try again."), 500
    finally:
        if temporary_path and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                logger.exception("Could not delete temporary upload %s", temporary_path)


@api.get("/history")
def history():
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    rows = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return jsonify(submissions=[_submission_json(row) for row in rows])


@api.get("/reports/<int:submission_id>")
def get_report(submission_id):
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    submission = db.session.get(Submission, submission_id)
    if submission is None or (current_user.role != "lecturer" and submission.user_id != current_user.id):
        return jsonify(error="That report could not be found."), 404
    return jsonify(submission=_submission_json(submission, include_report=True))


@api.get("/reports/<int:submission_id>/pdf")
def report_pdf(submission_id):
    unauthorized = _require_user()
    if unauthorized:
        return unauthorized
    submission = db.session.get(Submission, submission_id)
    if submission is None or (current_user.role != "lecturer" and submission.user_id != current_user.id):
        return jsonify(error="That report could not be found."), 404
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import simpleSplit
        from reportlab.pdfgen import canvas
    except ImportError:
        logger.exception("ReportLab is unavailable for PDF export")
        return jsonify(error="PDF export is unavailable until ReportLab is installed."), 503

    report_data = json.loads(submission.report_json)
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=letter)
    _, height = letter
    y = height - 54
    page.setTitle(f"Assignment quality report - {submission.file_name}")
    page.setFont("Helvetica-Bold", 16)
    page.drawString(48, y, "Assignment Quality Report")
    y -= 28
    page.setFont("Helvetica", 10)
    lines = [
        f"File: {submission.file_name}",
        f"Overall quality score: {report_data['overall_score']}/100",
        f"Words: {report_data['writing']['counts']['words']}",
        "",
        "Actionable feedback:",
        *[f"- {item}" for item in report_data["feedback"]],
        "",
        "Category scores:",
        *[f"- {name}: {score}/100" for name, score in report_data["category_scores"].items()],
        "",
        report_data["ethics"],
    ]
    for line in lines:
        safe_line = line.encode("latin-1", "replace").decode("latin-1")
        for wrapped_line in simpleSplit(safe_line, "Helvetica", 10, 516) if safe_line else [""]:
            if y < 54:
                page.showPage()
                page.setFont("Helvetica", 10)
                y = height - 54
            page.drawString(48, y, wrapped_line)
            y -= 15
    page.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="assignment-quality-report.pdf")
