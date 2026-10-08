import pytest

from app import create_app, db
from app.models import User


@pytest.fixture
def app(tmp_path):
    application = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
    })
    with application.app_context():
        db.create_all()
        db.session.add(User(
            email="student@example.test",
            password_hash=User.hash_password("secure-test-password"),
            role="student",
        ))
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    test_client = app.test_client()
    with app.app_context():
        user = User.query.filter_by(email="student@example.test").one()
        user_id = user.id
    with test_client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return test_client
