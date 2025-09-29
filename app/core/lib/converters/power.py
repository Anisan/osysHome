def watts_to_va(watts, power_factor=0.8):
    """Преобразует Вт в ВА (вольт-амперы) с учетом коэффициента мощности."""
    return watts / power_factor

def va_to_watts(va, power_factor=0.8):
    """Преобразует ВА в Вт."""
    return va * power_factor

def wh_to_kwh(wh):
    """Преобразует Вт в кВт."""
    return wh / 1000.0

def kwh_to_wh(kwh):
    """Преобразует кВт в Вт."""
    return kwh * 1000.0
