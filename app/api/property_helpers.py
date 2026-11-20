"""Safe property reads for API endpoints (respect ObjectManager permissions)."""

from app.core.lib.entity_params import is_entity_visible


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
    return {
        'value': obj.getProperty(property_name),
        'source': obj.getProperty(property_name, 'source'),
        'changed': changed,
    }


def collect_object_property_values(obj, *, include_advanced: bool = False, include_hidden: bool = False):
    """Collect property values, skipping properties the caller cannot read."""
    data = {}
    for key, prop in obj.properties.items():
        if not is_entity_visible(
            getattr(prop, "params", None),
            include_advanced=include_advanced,
            include_hidden=include_hidden,
        ):
            continue
        try:
            data[key] = obj.getProperty(key)
        except PermissionError:
            continue
    return data
