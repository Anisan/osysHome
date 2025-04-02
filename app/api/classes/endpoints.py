from flask_restx import Namespace, Resource
from app.api.models import model_result, model_404
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_user_required
from app.core.models.Clasess import Class, Property, Method

classes_ns = Namespace(name="classes",description="Class namespace",validate=True)

response_result = classes_ns.model('Result', model_result)
response_404 = classes_ns.model('Error', model_404)

@classes_ns.route("/<class_name>")
class GetClass(Resource):
    @api_key_required
    @handle_user_required
    @classes_ns.doc(security="apikey")
    @classes_ns.response(200, "Retrieved class.", response_result)
    @classes_ns.response(404, 'Not Found', response_404)
    def get(self, class_name):
        '''
        Get class.
        '''
        item = Class.query.filter(Class.name == class_name).one_or_404()
        if item:
            cls = {}
            cls['description'] = item.description
            cls['properties'] = {}

            res = Property.query.filter(Property.class_id == item.id, Property.object_id.is_(None)).all()
            for prop in res:
                cls['properties'][prop.name] = prop.description
            cls['methods'] = {}
            res = Method.query.filter(Method.class_id == item.id, Method.object_id.is_(None))
            for method in res:
                cls['methods'][method.name] = method.description
            return {
                'success': True,
                'result': cls}, 200
        return {
            'success': False,
            'message': 'Class not found'}, 404
    
