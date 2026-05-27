import ast

from flask import request
from flask_restx import Namespace, Resource, fields

from app.api.decorators import api_key_required
from app.api.models import model_result, model_404
from app.authentication.handlers import handle_admin_required
from app.core.lib.execute import execute_and_capture_output
from app.core.main.CustomFunctionRegistry import custom_function_registry
from app.core.models.CustomFunctions import CustomFunction
from app.database import session_scope, row2dict, get_now_to_utc

custom_functions_ns = Namespace(
    name="custom_functions",
    description="CustomFunction namespace",
    validate=True,
)

response_result = custom_functions_ns.model('Result', model_result)
response_404 = custom_functions_ns.model('Error', model_404)

cf_model = custom_functions_ns.model(
    'CustomFunctionBody',
    {
        'name': fields.String(required=True),
        'description': fields.String(),
        'code': fields.String(),
        'test_code': fields.String(),
        'active': fields.Boolean(default=True),
        'order': fields.Integer(default=0),
    },
)

test_model = custom_functions_ns.model(
    'CustomFunctionTestBody',
    {
        'code': fields.String(description='Override test_code from DB'),
        'params': fields.Raw(description='params variable for test run'),
    },
)


def _row_to_dict(row):
    data = row2dict(row)
    data['has_error'] = row.name in custom_function_registry.get_compile_errors()
    data['exported_symbols'] = sorted(custom_function_registry.get_exported_symbols(row.name))
    return data


@custom_functions_ns.route("/list", endpoint="custom_functions_list")
class CustomFunctionsList(Resource):
    @api_key_required
    @handle_admin_required
    @custom_functions_ns.doc(security="apikey")
    @custom_functions_ns.response(200, "List CustomFunctions", response_result)
    def get(self):
        errors = custom_function_registry.get_compile_errors()
        with session_scope() as session:
            rows = session.query(CustomFunction).order_by(CustomFunction.order, CustomFunction.name).all()
            result = []
            for row in rows:
                item = {
                    'name': row.name,
                    'description': row.description,
                    'active': row.active,
                    'order': row.order,
                    'has_error': row.name in errors,
                    'exported_symbols': sorted(custom_function_registry.get_exported_symbols(row.name)),
                }
                if row.name in errors:
                    item['error'] = errors[row.name]
                result.append(item)
        return {'success': True, 'result': result}, 200


@custom_functions_ns.route("/reload", endpoint="custom_functions_reload")
class CustomFunctionsReload(Resource):
    @api_key_required
    @handle_admin_required
    @custom_functions_ns.doc(security="apikey")
    def post(self):
        custom_function_registry.reload_all()
        return {
            'success': True,
            'result': {
                'errors': custom_function_registry.get_compile_errors(),
            },
        }, 200


@custom_functions_ns.route("/<string:name>", endpoint="custom_function_item")
class CustomFunctionItem(Resource):
    @api_key_required
    @handle_admin_required
    @custom_functions_ns.doc(security="apikey")
    @custom_functions_ns.response(200, "CustomFunction", response_result)
    @custom_functions_ns.response(404, "Not Found", response_404)
    def get(self, name):
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if not row:
                return {'success': False, 'msg': 'CustomFunction not found.'}, 404
            return {'success': True, 'result': _row_to_dict(row)}, 200

    @api_key_required
    @handle_admin_required
    @custom_functions_ns.expect(cf_model, validate=False)
    @custom_functions_ns.doc(security="apikey")
    def put(self, name):
        payload = request.get_json(force=True, silent=True) or {}
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if not row:
                return {'success': False, 'msg': 'CustomFunction not found.'}, 404

            code = payload.get('code', row.code) or ''
            active = payload.get('active', row.active)
            if 'description' in payload:
                row.description = payload['description']
            if 'code' in payload:
                row.code = payload['code']
            if 'test_code' in payload:
                row.test_code = payload['test_code']
            if 'active' in payload:
                row.active = payload['active']
            if 'order' in payload:
                row.order = payload['order']

            try:
                ast.parse(code)
            except SyntaxError as ex:
                return {'success': False, 'msg': f'Syntax error: {ex}'}, 400

            ok, err, bindings = custom_function_registry.validate_exported_symbols(
                name, code, active=active
            )
            if not ok:
                return {'success': False, 'msg': err}, 400

            row.updated = get_now_to_utc()
            session.commit()

        if active:
            reload_ok = custom_function_registry.reload(name, precompiled=bindings)
        else:
            custom_function_registry.reload(name)
            reload_ok = True

        errors = custom_function_registry.get_compile_errors()
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one()
            result = _row_to_dict(row)
        return {
            'success': reload_ok,
            'result': result,
            'msg': errors.get(name),
            'errors': errors,
        }, 200 if reload_ok else 400

    @api_key_required
    @handle_admin_required
    @custom_functions_ns.doc(security="apikey")
    def delete(self, name):
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if not row:
                return {'success': False, 'msg': 'CustomFunction not found.'}, 404
            session.delete(row)
            session.commit()
        custom_function_registry.reload(name)
        return {'success': True, 'result': name}, 200


@custom_functions_ns.route("", endpoint="custom_function_create")
class CustomFunctionCreate(Resource):
    @api_key_required
    @handle_admin_required
    @custom_functions_ns.expect(cf_model, validate=True)
    @custom_functions_ns.doc(security="apikey")
    def post(self):
        payload = request.get_json(force=True, silent=True) or {}
        name = (payload.get('name') or '').strip()
        if not name:
            return {'success': False, 'msg': 'Name is required.'}, 400

        code = payload.get('code') or ''
        active = payload.get('active', True)

        try:
            ast.parse(code)
        except SyntaxError as ex:
            return {'success': False, 'msg': f'Syntax error: {ex}'}, 400

        ok, err, bindings = custom_function_registry.validate_exported_symbols(
            name, code, active=active
        )
        if not ok:
            return {'success': False, 'msg': err}, 400

        with session_scope() as session:
            existing = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if existing:
                return {'success': False, 'msg': 'CustomFunction already exists.'}, 409
            row = CustomFunction()
            row.name = name
            row.description = payload.get('description', '')
            row.code = code
            row.test_code = payload.get('test_code', '')
            row.active = active
            row.order = payload.get('order', 0) or 0
            row.updated = get_now_to_utc()
            session.add(row)
            session.commit()

        reload_ok = custom_function_registry.reload(
            name, precompiled=bindings if active else None
        )
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one()
            result = _row_to_dict(row)
        errors = custom_function_registry.get_compile_errors()
        return {
            'success': reload_ok,
            'result': result,
            'msg': errors.get(name),
        }, 201 if reload_ok else 400


@custom_functions_ns.route("/<string:name>/test", endpoint="custom_function_test")
class CustomFunctionTest(Resource):
    @api_key_required
    @handle_admin_required
    @custom_functions_ns.expect(test_model, validate=False)
    @custom_functions_ns.doc(security="apikey")
    def post(self, name):
        payload = request.get_json(force=True, silent=True) or {}
        with session_scope() as session:
            row = session.query(CustomFunction).filter(CustomFunction.name == name).one_or_none()
            if not row:
                return {'success': False, 'msg': 'CustomFunction not found.'}, 404
            test_code = payload.get('code') or row.test_code or ''

        if not test_code.strip():
            return {'success': False, 'msg': 'test_code is empty.'}, 400

        variables = {
            'params': payload.get('params'),
            'logger': __import__('app.logging_config', fromlist=['getLogger']).getLogger('custom_function_test'),
        }
        output, error = execute_and_capture_output(
            test_code,
            variables,
            code_filename=f'<Test:{name}>',
            method_context={'source': f'CustomFunction.test:{name}'},
        )
        return {
            'success': not error,
            'result': output,
            'error': error,
        }, 200
