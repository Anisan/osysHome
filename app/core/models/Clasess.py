from sqlalchemy import ForeignKey
from app.database import Column, Model, SurrogatePK, db, relationship

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
    history = Column(db.Integer, default = 0)
    # TODO type and validator
    type = Column(db.String(100))

class Method(SurrogatePK, db.Model):
    __tablename__ = 'methods'
    name = Column(db.String(255), nullable=False)
    description = Column(db.String(512))
    class_id = Column(db.Integer)
    object_id = Column(db.Integer)
    code = Column(db.Text)
    call_parent= Column(db.Integer)

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
    value_id = Column(db.Integer)
    value = Column(db.Text)
    added = Column(db.DateTime())
    source = Column(db.Text)
