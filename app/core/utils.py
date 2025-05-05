from datetime import datetime
from json import JSONEncoder, dumps as json_dumps
from flask.json.provider import DefaultJSONProvider

class CustomJSONEncoder(JSONEncoder):
    """
    Custom encoder for handling default values from a function call.
    Formats datetime objects using a specified format, including milliseconds.
    """
    def __init__(self, date_format="%Y-%m-%d %H:%M:%S", include_milliseconds=True, *args, **kwargs):
        """
        Initialize the encoder with an optional date format and millisecond inclusion flag.

        :param date_format: The base format string for datetime objects.
        :param include_milliseconds: Whether to include milliseconds in the output.
        """
        super().__init__(*args, **kwargs)
        self.date_format = date_format
        self.include_milliseconds = include_milliseconds

    def default(self, o):
        """
        Override the default method to handle datetime objects.
        """
        if isinstance(o, datetime):
            # Format the datetime object using the specified format
            formatted_date = o.strftime(self.date_format)
            if self.include_milliseconds:
                # Append milliseconds (first 3 digits of microseconds)
                milliseconds = f"{o.microsecond:06d}"[:3]
                formatted_date += f".{milliseconds}"
            return formatted_date
        # Let the base class handle other types
        return super().default(o)
    
class CustomJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        # Используем CustomJSONEncoder для сериализации
        return json_dumps(obj, cls=CustomJSONEncoder, **kwargs)

def truncate_string(input_string, length, suffix='...'):
    if len(input_string) <= length:
        return input_string
    return input_string[:length] + suffix
