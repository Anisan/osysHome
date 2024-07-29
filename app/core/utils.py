from json import JSONEncoder
import datetime

class CustomJSONEncoder(JSONEncoder):
    """Custom encoder for handling default values from a function call"""
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)