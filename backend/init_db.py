"""Initialise the database and create a demo user.

Run once after cloning:
    cd backend
    python init_db.py
"""
from app import create_app
from app.extensions import db
from app.models import Chat, Citation, Document, Message, User

app = create_app()

with app.app_context():
    print("Creating database tables...")
    db.create_all()
    print("Tables created.")

    if User.query.first() is None:
        print("Seeding demo user...")
        user = User(name="Demo User", email="demo@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        print("Demo user created: demo@example.com / password123")
    else:
        print("Users already exist — skipping seed.")

    print("Done.")
