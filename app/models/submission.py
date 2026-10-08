from app import db


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    extracted_text = db.Column(db.Text, nullable=False)
    report_json = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, nullable=False)
    quality_score = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), index=True)
    user = db.relationship("User", back_populates="submissions")
