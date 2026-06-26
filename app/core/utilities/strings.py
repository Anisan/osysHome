def truncate_string(input_string, length, suffix='...'):
    if len(input_string) <= length:
        return input_string
    return input_string[:length] + suffix
