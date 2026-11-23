from flask import request
from flask_restx import Namespace, Resource, fields
from app.api.models import (
    model_404,
    model_class_summary,
    wrap_result,
)
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required
from app.core.lib.entity_params import is_entity_visible, parse_bool_flag
from app.core.models.Clasess import Class, Property, Method

classes_ns = Namespace(
    name="classes",
    description="Class metadata: properties and methods descriptions",
    validate=True,
)

class_summary = classes_ns.model('ClassSummary', model_class_summary)
response_class = classes_ns.model(
    'ResultClass',
    wrap_result(fields.Nested(class_summary, description='Class summary')),
)
response_404 = classes_ns.model('Error', model_404)


@classes_ns.route("/<class_name>")
class GetClass(Resource):
    @api_key_required
    @handle_user_required
    @classes_ns.doc(security="apikey", description="Get class properties and methods descriptions")
    @classes_ns.param("advanced", "Include advanced properties/methods (params.advanced). Default: false", _in="query")
    @classes_ns.param("hidden", "Include hidden properties/methods (params.hidden). Default: false", _in="query")
    @classes_ns.response(200, "Retrieved class.", response_class)
    @classes_ns.response(404, 'Not Found', response_404)
    def get(self, class_name):
        '''
        Get class description with property and method name maps.
        '''
        include_advanced = parse_bool_flag(request.args.get("advanced"))
        include_hidden = parse_bool_flag(request.args.get("hidden"))
        item = Class.query.filter(Class.name == class_name).one_or_none()
        if not item:
            return {
                'success': False,
                'msg': 'Class not found'}, 404
        cls = {}
        cls['description'] = item.description
        cls['properties'] = {}

        res = Property.query.filter(Property.class_id == item.id, Property.object_id.is_(None)).all()
        for prop in res:
            if not is_entity_visible(
                getattr(prop, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            cls['properties'][prop.name] = prop.description
        cls['methods'] = {}
        res = Method.query.filter(Method.class_id == item.id, Method.object_id.is_(None))
        for method in res:
            if not is_entity_visible(
                getattr(method, "params", None),
                include_advanced=include_advanced,
                include_hidden=include_hidden,
            ):
                continue
            cls['methods'][method.name] = method.description
        return {
            'success': True,
            'result': cls}, 200
