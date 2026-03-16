# backend/app/database/alchemyDatabaseUpdate.py

"""
This file contains the functions to update the database.
"""

from app.database.database import engine, Session, Base
from app.database.models.usersTable import User
import uuid

def create_tables():
    Base.metadata.create_all(engine)

def delete_tables():
    Base.metadata.drop_all(engine)

def add_test_user():
    with Session() as session:
        user = User(
            id=uuid.uuid4(),
            first_name='Test',
            last_name='User',
            email='test@example.com',
            phone={'country_code': '+33', 'number': '1234567890'},
            password_hash='password',
        )
        session.add(user)
        session.commit()

def delete_test_user():
    with Session() as session:
        session.query(User).filter(User.email == 'test@example.com').delete()
        session.commit()

if __name__ == '__main__':
    create_tables()
    add_test_user()
    # delete_test_user()
    # delete_tables()