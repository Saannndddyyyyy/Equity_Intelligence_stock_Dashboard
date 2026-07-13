import sys
import os

# Append current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base

# Ensure models are imported so SQLAlchemy knows about them


def init_database():
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    init_database()
