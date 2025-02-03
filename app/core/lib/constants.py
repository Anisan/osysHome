""" Constants """
from enum import Enum

class CategoryNotify(Enum):
    """ Category notify """
    Debug = 0
    Info = 1
    Warning = 2
    Error = 3
    Fatal = 4

class PropertyType(Enum):
    """ Types property """
    Empty = ''
    String = 'str'
    Integer = 'int'
    Float = 'float'
    Datetime = 'datetime'
    Dictionary = 'dict'
    List = 'list'
    Bool = 'bool'
    
