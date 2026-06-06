"""Safe property reads for API endpoints (respect ObjectManager permissions)."""
from app.database import convert_utc_to_local


def read_property_value(obj, property_name):
    """Return a property value through permission checks."""
    if property_name == 'description':
        return obj.description
    if property_name == 'template':
        return obj.template
    return obj.getProperty(property_name)


def read_property_details(obj, property_name):
    """Return property value with source/changed metadata."""
    if property_name == 'description':
        return {'value': obj.description, 'source': None, 'changed': None}
    if property_name == 'template':
        return {'value': obj.template, 'source': None, 'changed': None}
    if property_name not in obj.properties:
        raise KeyError(property_name)
    changed = obj.getProperty(property_name, 'changed')
    if changed is not None:
        changed = convert_utc_to_local(changed)
    return {
        'value': obj.getProperty(property_name),
        'source': obj.getProperty(property_name, 'source'),
        'changed': changed,
    }


def collect_object_property_values(obj):
    """Collect property values, skipping properties the caller cannot read."""
    data = {}
    for key in obj.properties:
        try:
            data[key] = obj.getProperty(key)
        except PermissionError:
            continue
    return data
