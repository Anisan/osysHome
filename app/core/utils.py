from json import JSONEncoder
import datetime

class CustomJSONEncoder(JSONEncoder):
    """Custom encoder for handling default values from a function call"""
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)
        return super().default(o)
    
def truncate_string(input_string, length, suffix='...'):
    if len(input_string) <= length:
        return input_string
    return input_string[:length] + suffix