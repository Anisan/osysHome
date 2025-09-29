def pascals_to_mmhg(pascals):
    """
    Преобразует давление из Паскалей в мм рт. ст.

    Args:
        pascals (float): давление в Паскалях

    Returns:
        float: давление в мм рт. ст.
    """
    return pascals * 0.00750062


def mmhg_to_pascals(mmhg):
    """
    Преобразует давление из мм рт. ст. в Паскали.

    Args:
        mmhg (float): давление в мм рт. ст.

    Returns:
        float: давление в Паскалях
    """
    return mmhg / 0.00750062

def hpa_to_mmhg(hpa):
    """Преобразует давление из гПа в мм рт. ст."""
    return hpa * 0.750062

def mmhg_to_hpa(mmhg):
    """Преобразует давление из мм рт. ст. в гПа."""
    return mmhg / 0.750062

def hpa_to_inhg(hpa):
    """Преобразует давление из гПа в дюймы рт. ст."""
    return hpa * 0.02953

def inhg_to_hpa(inhg):
    """Преобразует давление из дюймов рт. ст. в гПа."""
    return inhg / 0.02953
