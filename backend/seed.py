"""Initialize the local database schema without creating shared demo accounts."""

from app.database import Base, engine
from app import models  # noqa: F401 - registers models with SQLAlchemy metadata


def run() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database schema ready. Create a user through the signup page.")


if __name__ == "__main__":
    run()
