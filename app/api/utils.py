from app.core.models.Clasess import Class

def getClassWithParents(class_id):
    classes = []
    cls = Class.get_by_id(class_id)
    if cls.parent_id:
        parent = getClassWithParents(cls.parent_id)
        classes += parent
    classes.append(cls)
    return classes