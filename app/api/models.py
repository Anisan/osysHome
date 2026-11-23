"""Общие словари полей для flask-restx моделей ответов API.

Словари регистрируются в Namespace через ``ns.model(...)``.
Для Nested-обёрток создавайте entity-модель в namespace, затем ResultOf*.
"""
from flask_restx import fields

# --- Базовые обёртки ---

model_404 = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'msg': fields.String(description='Error message'),
}

model_result = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='Result of the request'),
}

model_success = {
    'success': fields.Boolean(description='Indicates success of the operation'),
}

model_message = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'message': fields.String(description='Status or error message'),
}

model_error_msg = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'msg': fields.String(description='Error message'),
}

model_error_message = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'message': fields.String(description='Error message'),
}

model_error_error = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'error': fields.String(description='Error details'),
}

model_forbidden = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'msg': fields.String(description='Forbidden reason', example='Forbidden.'),
}

# --- Сущности: объекты / классы ---

model_object_summary = {
    'description': fields.String(description='Object description'),
    'properties': fields.Raw(
        description='Map of property name to description string',
    ),
    'methods': fields.Raw(
        description='Map of method name to description string',
    ),
}

model_class_summary = {
    'description': fields.String(description='Class description'),
    'properties': fields.Raw(
        description='Map of property name to description string',
    ),
    'methods': fields.Raw(
        description='Map of method name to description string',
    ),
}

model_object_data = {
    'name': fields.String(description='Object name'),
    'description': fields.String(description='Object description'),
}

model_object_by_class_item = {
    'name': fields.String(description='Object name'),
    'description': fields.String(description='Object description'),
    'properties': fields.Raw(
        description='Map of property name to current value',
    ),
}

# --- Свойства ---

model_property_details = {
    'value': fields.Raw(description='Current property value'),
    'source': fields.String(description='Last change source', allow_null=True),
    'changed': fields.Raw(description='Last change timestamp', allow_null=True),
}

model_property_info = {
    'id': fields.Integer(description='Property id'),
    'name': fields.String(description='Property name'),
    'description': fields.String(description='Property description'),
    'type': fields.String(description='Property type'),
    'object_id': fields.Integer(description='Object id', allow_null=True),
    'object_name': fields.String(description='Object name'),
    'object_description': fields.String(description='Object description'),
    'value_id': fields.Integer(description='Value row id', allow_null=True),
    'history': fields.Raw(description='History settings'),
    'linked': fields.Raw(description='Linked properties'),
    'method': fields.String(description='Bound method name', allow_null=True),
    'params': fields.Raw(description='Property params'),
}

model_property_set_body = {
    'data': fields.Raw(required=True, description='Value to set'),
    'source': fields.String(description='Change source', default='api'),
}

model_history_delete = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'message': fields.String(description='Status message'),
}

# --- Методы ---

model_method_call_result = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'args': fields.Raw(description='Request arguments'),
    'result': fields.Raw(description='Method return value (text or parsed JSON)'),
}

# --- About / user ---

model_about = {
    'name': fields.String(description='Application name'),
    'author': fields.String(description='Author'),
    'version': fields.String(description='Application version'),
    'email': fields.String(description='Contact email'),
}

model_user_result = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='Current user dict'),
}

# --- Utils ---

model_search_item = {
    'url': fields.String(description='Result URL'),
    'title': fields.String(description='Result title'),
    'tags': fields.List(fields.String, description='Result tags'),
}

model_search_module_error = {
    'module': fields.String(description='Plugin/module name'),
    'error': fields.String(description='Error message'),
}

model_search_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'items': fields.List(fields.Raw, description='Search result items'),
    'count': fields.Integer(description='Number of items'),
    'errors': fields.List(fields.Raw, description='Per-module search errors'),
}

model_mute_created = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'mute_id': fields.String(description='Created mute identifier'),
}

model_error_rate_mute_list = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'items': fields.List(fields.Raw, description='Mute entries'),
    'count': fields.Integer(description='Number of mute entries'),
}

model_validate_python_error = {
    'row': fields.Integer(description='0-based row index'),
    'column': fields.Integer(description='0-based column index'),
    'text': fields.String(description='Error text'),
    'type': fields.String(description='Error type', example='error'),
}

model_intelli_response = {
    'symbols': fields.List(fields.Raw, description='IntelliSense symbol cache entries'),
}

model_lsp_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'error': fields.String(description='Error message when failed', required=False),
}

model_run_code_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='Stdout/result or exception'),
}

model_cron_validate_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'ok': fields.Boolean(description='Whether cron expression is valid'),
    'timezone': fields.String(description='Server timezone'),
    'next_runs': fields.List(fields.String, description='Upcoming run times'),
    'error': fields.String(description='Validation error', required=False),
}

model_notifications_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'notifications': fields.List(fields.Raw, description='Notification items'),
}

model_notification_source_stat = {
    'source': fields.String(description='Notification source'),
    'total': fields.Integer(description='Total notifications from source'),
    'unread': fields.Integer(description='Unread count from source'),
}

model_notification_stats = {
    'total': fields.Integer(description='Total notifications'),
    'unread': fields.Integer(description='Unread notifications'),
    'sources': fields.List(fields.Raw, description='Per-source statistics'),
}

model_notification_stats_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'stats': fields.Raw(description='Notification statistics'),
}

model_analytics_get = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'analytics_enabled': fields.String(
        description='disabled | basic | extended, or null/empty if not asked',
        allow_null=True,
    ),
    'asked': fields.Boolean(description='Whether user has set a preference'),
}

model_analytics_set = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'analytics_enabled': fields.String(description='disabled | basic | extended'),
}

# --- SQL ---

model_sql_select_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.List(fields.Raw, description='Selected rows as dictionaries'),
}

model_sql_exec_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'error': fields.String(description='Error details when failed', required=False),
}

model_sql_mutate_response = {
    'success': fields.Raw(description='Boolean or driver result'),
    'error': fields.String(description='Error details when failed', required=False),
}

# --- Export / Import ---

model_export_class_item = {
    'name': fields.String(description='Class name'),
    'description': fields.String(description='Class description'),
    'template': fields.String(description='Class template', allow_null=True),
    'parent': fields.String(description='Parent class name', allow_null=True),
    'params': fields.Raw(description='Class params'),
}

model_export_property_item = {
    'name': fields.String(description='Property name'),
    'description': fields.String(description='Property description'),
    'history': fields.Raw(description='History settings'),
    'type': fields.String(description='Property type'),
    'class_method': fields.String(description='Class of bound method', allow_null=True),
    'method': fields.String(description='Bound method name', allow_null=True),
    'class': fields.String(description='Owning class name', allow_null=True),
    'object': fields.String(description='Owning object name', allow_null=True),
    'params': fields.Raw(description='Property params'),
}

model_export_method_item = {
    'name': fields.String(description='Method name'),
    'description': fields.String(description='Method description'),
    'code': fields.String(description='Method code'),
    'class': fields.String(description='Owning class name', allow_null=True),
    'object': fields.String(description='Owning object name', allow_null=True),
    'params': fields.Raw(description='Method params'),
}

model_export_object_item = {
    'name': fields.String(description='Object name'),
    'description': fields.String(description='Object description'),
    'class': fields.String(description='Class name', allow_null=True),
    'template': fields.String(description='Object template', allow_null=True),
    'params': fields.Raw(description='Object params'),
}

model_export_payload = {
    'classes': fields.List(fields.Raw, description='Exported classes'),
    'objects': fields.List(fields.Raw, description='Exported objects'),
    'properties': fields.List(fields.Raw, description='Exported properties'),
    'methods': fields.List(fields.Raw, description='Exported methods'),
    'values': fields.List(fields.Raw, description='Exported property values'),
}

model_import_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'message': fields.String(description='Import status message'),
}

model_import_stream_event = {
    'event': fields.String(description='Event type: progress | done | error'),
    'success': fields.Boolean(description='Present on done event', required=False),
    'message': fields.String(description='Event message', required=False),
}

# --- Custom functions ---

model_custom_function_list_item = {
    'name': fields.String(description='Function name'),
    'description': fields.String(description='Function description'),
    'active': fields.Boolean(description='Whether function is active'),
    'order': fields.Integer(description='Sort order'),
    'has_error': fields.Boolean(description='Whether compile error exists'),
    'exported_symbols': fields.List(fields.String, description='Exported symbol names'),
    'error': fields.String(description='Compile error text', required=False),
}

model_custom_function_detail = {
    'id': fields.Integer(description='Row id', required=False),
    'name': fields.String(description='Function name'),
    'description': fields.String(description='Function description'),
    'code': fields.String(description='Function code'),
    'test_code': fields.String(description='Test code'),
    'active': fields.Boolean(description='Whether function is active'),
    'order': fields.Integer(description='Sort order'),
    'updated': fields.Raw(description='Last update timestamp', required=False),
    'has_error': fields.Boolean(description='Whether compile error exists'),
    'exported_symbols': fields.List(fields.String, description='Exported symbol names'),
}

model_custom_function_reload = {
    'errors': fields.Raw(description='Map of function name to compile error'),
}

model_custom_function_write_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='CustomFunction detail dict'),
    'msg': fields.String(description='Error or compile message', required=False),
    'errors': fields.Raw(description='Compile errors map', required=False),
}

model_custom_function_test_response = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='Test output'),
    'error': fields.String(description='Error output when failed', allow_null=True),
}


def wrap_result(result_field):
    """Собрать обёртку {success, result} с заданным полем result."""
    return {
        'success': fields.Boolean(description='Indicates success of the operation'),
        'result': result_field,
    }
