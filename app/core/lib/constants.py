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
    Enum = 'enum'
    Color = 'color'


# Internal SystemStats object — source marker for anti-loop analytics
SYSTEM_STATS_OBJECT = "SystemStats"
SYSTEM_STATS_SOURCE = "osysHome:system_stats"
SYSTEM_STATS_EXCLUDED_OBJECTS = frozenset({SYSTEM_STATS_OBJECT, "_permissions"})
SYSTEM_STATS_PLUGIN_METRIC_PREFIX = "plugin_"

