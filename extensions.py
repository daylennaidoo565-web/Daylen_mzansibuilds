from flask_sqlalchemy import SQLAlchemy

# db is created here — imported by both app.py and models.py
# This breaks the circular import between app.py and models.py
db = SQLAlchemy()