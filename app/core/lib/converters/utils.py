import json

def json_to_dict(json_str):
    """
    Преобразует JSON-строку в словарь Python.

    Args:
        json_str (str): строка в формате JSON

    Returns:
        dict: словарь Python
    """
    return json.loads(json_str)


def dict_to_json(data):
    """
    Преобразует словарь Python в JSON-строку.

    Args:
        data: любой сериализуемый объект

    Returns:
        str: строка в формате JSON
    """
    return json.dumps(data)


def percent_to_decimal(percent):
    """
    Преобразует процент (строку или число) в десятичную дробь.

    Args:
        percent: строка вида "75%" или число

    Returns:
        float: десятичная дробь
    """
    if isinstance(percent, str):
        percent = percent.strip().rstrip("%")
    return float(percent) / 100.0


def decimal_to_percent(decimal, with_symbol=False):
    """
    Преобразует десятичную дробь в процент.

    Args:
        decimal (float): дробь от 0 до 1
        with_symbol (bool): добавить ли символ '%'

    Returns:
        float or str: процент
    """
    p = decimal * 100
    return f"{p}%" if with_symbol else p


def percent_of(percent, max_value):
    """
    Вычисляет абсолютное значение по проценту от заданного максимума (100%).

    Args:
        percent: строка вида "75%" или число
        max_value (float): максимальное значение (100%)

    Returns:
        float: абсолютное значение
    """
    ratio = percent_to_decimal(percent)
    return ratio * max_value


def value_to_percent(value, max_value, with_symbol=False):
    """
    Вычисляет, какой процент составляет value от max_value.

    Args:
        value (float): текущее значение
        max_value (float): максимальное значение
        with_symbol (bool): добавить ли символ '%'

    Returns:
        float or str: процент
    """
    if max_value == 0:
        raise ValueError("max_value не может быть 0 при вычислении процента")
    ratio = value / max_value
    return decimal_to_percent(ratio, with_symbol)
