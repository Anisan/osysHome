from sqlalchemy import ForeignKey, func, desc, asc, Index
from app.database import Column, SurrogatePK, db, relationship

class Class(SurrogatePK, db.Model):
    """ Model Class

    Args:
        SurrogatePK (_type_): _description_
        db (_type_): _description_
    """
    __tablename__ = 'classes'
    name = Column(db.String(255), unique=True, nullable=False)
    description = Column(db.String(512))
    parent_id = Column(db.Integer)
    template = Column(db.Text)
    objects = relationship("Object", back_populates="class_")

class Object(SurrogatePK, db.Model):
    """Model Object

    Args:
        SurrogatePK (_type_): _description_
        db (_type_): _description_
    """
    __tablename__ = 'objects'
    name = Column(db.String(255), unique=True, nullable=False)
    description = Column(db.String(512))
    class_id = Column(db.Integer, ForeignKey('classes.id', name='fk_object_class_id'))
    class_ = relationship("Class", back_populates="objects")
    template = Column(db.Text)
    properties = relationship("Property", back_populates="object_")

class Property(SurrogatePK, db.Model):
    """ Model Property

    Args:
        SurrogatePK (_type_): _description_
        db (_type_): _description_
    """
    __tablename__ = 'properties'
    name = Column(db.String(255), nullable=False)
    description = Column(db.String(512))
    class_id = Column(db.Integer)
    object_id = Column(db.Integer, ForeignKey('objects.id', name='fk_object_property_id'))
    object_ = relationship("Object", back_populates="properties")
    method_id = Column(db.Integer)
    history = Column(db.Integer, default=0)
    # TODO type and validator
    type = Column(db.String(100))
    params = Column(db.Text)  # JSON parameters for property (e.g., enum values)

class Method(SurrogatePK, db.Model):
    __tablename__ = 'methods'
    name = Column(db.String(255), nullable=False)
    description = Column(db.String(512))
    class_id = Column(db.Integer)
    object_id = Column(db.Integer)
    code = Column(db.Text)
    call_parent = Column(db.Integer)

class Value(SurrogatePK, db.Model):
    __tablename__ = 'values'
    object_id = Column(db.Integer)
    name = Column(db.String(255))
    value = Column(db.Text)
    changed = Column(db.DateTime())
    linked = Column(db.String(512))
    source = Column(db.Text)

class History(SurrogatePK, db.Model):
    __tablename__ = 'history'
    value_id = Column(db.Integer, index=True)
    value = Column(db.Text)
    added = Column(db.DateTime())
    source = Column(db.Text)

    __table_args__ = (
        Index('ix_value_id_added', 'value_id', 'added'),
    )

    @staticmethod
    def getHistory(session, value_id, dt_begin=None, dt_end=None, limit=None, order_desc=False, func=None):
        query = session.query(History).filter_by(value_id=value_id)

        if dt_begin:
            query = query.filter(History.added >= dt_begin)
        if dt_end:
            query = query.filter(History.added <= dt_end)

        if order_desc:
            query = query.order_by(desc(History.added))
        else:
            query = query.order_by(asc(History.added))

        if limit:
            query = query.limit(limit)

        result = query.all()

        if func:
            result = [func(r) for r in result]

        return result

    @staticmethod
    def get_count(session, value_id, dt_begin=None, dt_end=None):
        query = session.query(func.count(History.value).label('count')).filter_by(value_id=value_id) # noqa
        if dt_begin:
            query = query.filter(History.added >= dt_begin)
        if dt_end:
            query = query.filter(History.added <= dt_end)
        return query.scalar()

    @staticmethod
    def delete_by_id(session, id):
        entry = session.query(History).filter_by(id=id).first()
        if entry:
            session.delete(entry)
            session.commit()
            return True
        return False

    @staticmethod
    def delete_by_filter(session, value_id, dt_begin=None, dt_end=None):
        query = session.query(History).filter_by(value_id=value_id)

        if dt_begin:
            query = query.filter(History.added >= dt_begin)
        if dt_end:
            query = query.filter(History.added <= dt_end)

        deleted_count = query.delete(synchronize_session=False)
        session.commit()
        return deleted_count
