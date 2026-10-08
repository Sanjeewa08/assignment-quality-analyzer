import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from . import db
from .analyzers.rubric import parse_rubric
from .extractors import ExtractionError, extract_document
from .models import Rubric, Submission, User
from .services.analysis import analyze_assignment

logger = logging.getLogger(__name__)
main = Blueprint("main", __name__)


def _requested_int(key):
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


@main.get("/")
def index():
    rubrics = Rubric.query.order_by(Rubric.title.asc()).all() if current_user.is_authenticated else []
    return render_template("index.html", rubrics=rubrics)


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or "@" not in email or len(email) > 255:
            flash("Enter a valid email address.", "error")
        elif len(password) < 10:
            flash("Use a password with at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(email=email, password_hash=User.hash_password(password), role="student")
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("main.index"))
    return render_template("auth.html", mode="register")


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=bool(request.form.get("remember")))
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//") and not urlsplit(next_url).netloc:
                return redirect(next_url)
            return redirect(url_for("main.index"))
        flash("Email or password was not recognized.", "error")
    return render_template("auth.html", mode="login")


@main.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@main.post("/analyze")
@login_required
def analyze():
    uploaded = request.files.get("assignment")
    if uploaded is None or not uploaded.filename:
        flash("Please choose a file to analyze.", "error")
        return redirect(url_for("main.index"))
    safe_name = secure_filename(uploaded.filename)
    if not safe_name:
        flash("The filename is invalid. Rename the file and try again.", "error")
        return redirect(url_for("main.index"))
    extension = Path(safe_name).suffix.lower()
    if extension not in current_app.extensions["extractor_extensions"]:
        flash("This file type is not supported. Upload TXT, DOCX, PDF, PPT, PPTX, JPG, JPEG, or PNG.", "error")
        return redirect(url_for("main.index"))

    temporary_path = None
    try:
        minimum = _requested_int("min_words")
        maximum = _requested_int("max_words")
        min_references = _requested_int("min_references")
        if minimum and maximum and minimum > maximum:
            raise ValueError("Minimum word count cannot exceed maximum word count.")
        rubric_id = request.form.get("rubric_id", "").strip()
        rubric = db.session.get(Rubric, int(rubric_id)) if rubric_id.isdigit() else None
        if rubric_id and rubric is None:
            raise ValueError("The selected rubric could not be found.")

        upload_dir = current_app.config["UPLOAD_FOLDER"]
        suffix = Path(safe_name).suffix.lower()
        handle = tempfile.NamedTemporaryFile(prefix="assignment-", suffix=suffix, dir=upload_dir, delete=False)
        temporary_path = Path(handle.name)
        handle.close()
        uploaded.save(temporary_path)
        document = extract_document(temporary_path)
        if not document.text.strip():
            raise ExtractionError("No readable text was found in this file. Scanned files require working OCR tools.")
        if len(document.text) > 1_000_000:
            raise ExtractionError("The extracted document is unusually large. Split it into smaller files and try again.")
        reference_text = request.form.get("reference_text", "")
        prior = (
            Submission.query.filter(Submission.extracted_text != "")
            .order_by(Submission.created_at.desc())
            .limit(25)
            .all()
        )
        comparisons = [
            ("another local submission", item.extracted_text[:100_000])
            for item in prior
        ]
        if rubric:
            criteria = json.loads(rubric.criteria_json)
        else:
            criteria = []
        report = analyze_assignment(
            document.text,
            formatting=document.formatting,
            min_words=minimum,
            max_words=maximum,
            other_submissions=comparisons,
            reference_text=reference_text,
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
        return redirect(url_for("main.report", submission_id=submission.id))
    except (ExtractionError, ValueError) as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("main.index"))
    except Exception:
        db.session.rollback()
        logger.exception("Assignment analysis failed for user %s", current_user.get_id())
        flash("We could not analyze this file. Check that it is valid and try again.", "error")
        return redirect(url_for("main.index"))
    finally:
        if temporary_path and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                logger.exception("Could not delete temporary upload %s", temporary_path)


def _visible_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if submission is None:
        abort(404)
    if current_user.role != "lecturer" and submission.user_id != current_user.id:
        abort(404)
    return submission


@main.get("/report/<int:submission_id>")
@login_required
def report(submission_id):
    submission = _visible_submission(submission_id)
    return render_template(
        "report.html",
        submission=submission,
        report=json.loads(submission.report_json),
    )


@main.get("/report/<int:submission_id>/pdf")
@login_required
def export_pdf(submission_id):
    submission = _visible_submission(submission_id)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import simpleSplit
    except ImportError as exc:
        logger.exception("ReportLab is unavailable for PDF export")
        abort(503, description="PDF export is unavailable until ReportLab is installed.")
    from io import BytesIO

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
        wrapped = simpleSplit(safe_line, "Helvetica", 10, 516) if safe_line else [""]
        for wrapped_line in wrapped:
            if y < 54:
                page.showPage()
                page.setFont("Helvetica", 10)
                y = height - 54
            page.drawString(48, y, wrapped_line)
            y -= 15
    page.save()
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="assignment-quality-report.pdf")


@main.get("/history")
@login_required
def history():
    submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.asc()).all()
    return render_template("history.html", submissions=submissions)


@main.route("/rubrics", methods=["GET", "POST"])
@login_required
def rubrics():
    if current_user.role != "lecturer":
        abort(403)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        criteria_text = request.form.get("criteria", "")
        criteria = parse_rubric(criteria_text)
        if not title or len(title) > 120:
            flash("Enter a rubric title up to 120 characters.", "error")
        elif not criteria:
            flash("Add at least one criterion, one per line.", "error")
        else:
            db.session.add(Rubric(
                author_id=current_user.id,
                title=title,
                criteria_json=json.dumps(criteria),
            ))
            db.session.commit()
            flash("Rubric saved. Unrecognized criterion lines will be marked for manual review.", "success")
            return redirect(url_for("main.rubrics"))
    rows = Rubric.query.filter_by(author_id=current_user.id).order_by(Rubric.title.asc()).all()
    return render_template("rubrics.html", rubrics=rows)


@main.app_errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@main.app_errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page or report could not be found."), 404
