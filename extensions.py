# The database is created here — imported by both app.py and models.py
# The purpose of this file is to prevent the circular import between app.py and models.py
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()