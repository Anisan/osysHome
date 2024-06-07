from app.database import Column, Model, SurrogatePK, db

class Task(SurrogatePK, db.Model):
    __tablename__ = 'tasks'
    name = Column(db.String(255), unique=True, nullable=False)
    code = Column(db.Text(), nullable=False)
    runtime = Column(db.DateTime, nullable=False)
    expire = Column(db.DateTime, nullable=False)
    started = Column(db.DateTime)
    crontab = Column(db.String(100))