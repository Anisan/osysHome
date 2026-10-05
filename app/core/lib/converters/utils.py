"""JSON and percentage conversion helpers."""
import json

def json_to_dict(json_str):
    """Parse a JSON string into a Python object.

    Args:
        json_str (str): JSON string

    Returns:
        Any: Parsed Python object (typically dict/list)
    """
    return json.loads(json_str)


def dict_to_json(data):
    """Serialize a Python object to a JSON string.

    Args:
        data: JSON-serializable object

    Returns:
        str: JSON string
    """
    return json.dumps(data)


def percent_to_decimal(percent):
    """Convert a percent (string or number) to a 0..1 fraction.

    Args:
        percent: Number or string like ``\"75%\"``

    Returns:
        float: Decimal fraction
    """
    if isinstance(percent, str):
        percent = percent.strip().rstrip("%")
    return float(percent) / 100.0


def decimal_to_percent(decimal, with_symbol=False):
    """Convert a 0..1 fraction to a percent.

    Args:
        decimal (float): Fraction from 0 to 1
        with_symbol (bool, optional): If True, return a string with ``%``.
            Defaults to False.

    Returns:
        float | str: Percent value or formatted string
    """
    p = decimal * 100
    return f"{p}%" if with_symbol else p


def percent_of(percent, max_value):
    """Compute an absolute value as a percent of a maximum.

    Args:
        percent: Number or string like ``\"75%\"``
        max_value (float): Value that represents 100%

    Returns:
        float: Absolute value
    """
    ratio = percent_to_decimal(percent)
    return ratio * max_value


def value_to_percent(value, max_value, with_symbol=False):
    """Compute what percent ``value`` is of ``max_value``.

    Args:
        value (float): Current value
        max_value (float): Maximum (100%)
        with_symbol (bool, optional): If True, return a string with ``%``.
            Defaults to False.

    Returns:
        float | str: Percent value or formatted string

    Raises:
        ValueError: If ``max_value`` is 0
    """
    if max_value == 0:
        raise ValueError("max_value не может быть 0 при вычислении процента")
    ratio = value / max_value
    return decimal_to_percent(ratio, with_symbol)
