"""API blueprint configuration."""
from flask import Blueprint, render_template
from flask_restx import Api, Resource
from app.logging_config import getLogger
from app.api.decorators import *
from app.api.objects.endpoints import objects_ns
from app.api.properties.endpoints import props_ns
from app.api.methods.endpoints import methods_ns
from app.api.utils.endpoints import utils_ns
from app.api.export.endpoints import export_ns
from app.api.import_.endpoints import import_ns

_logger = getLogger("api")

api_blueprint = Blueprint("api", __name__, url_prefix="/api")

# Объект authorizations для Swagger документации
authorizations = {
    'apikey': {
        'type': 'apiKey',
        'in': 'query',  # API ключ будет передаваться как параметр запроса
        'name': 'apikey'
    }
}

api = Api(
    api_blueprint,
    version="1.0",
    title="osysHome API",
    description="Welcome to osysHome API documentation site!",
    doc="/",
    authorizations=authorizations,
    security='apikey',
)

@api.route('/about')
class AboutResource(Resource):
    @api.doc(security=None)
    def get(self):
        '''
        Get about information.
        '''
        return {
            'name': 'osysHome',
            'author': 'Eraser',
            'email':'eraser1981@gmail.com',
        }

@api.route('/user')
class CurrentUserResource(Resource):
    @api_key_required
    @api.doc(security='apikey', description='Get current user information')
    def get(self):
        '''
        Get current user information
        '''
        user = g.current_user
        return {
            'success':True,
            'result': user.to_dict()}

api.add_namespace(objects_ns, path="/object")
api.add_namespace(props_ns, path="/property")
api.add_namespace(methods_ns, path="/method")
api.add_namespace(utils_ns, path="/utils")
api.add_namespace(export_ns, path="/export")
api.add_namespace(import_ns, path="/import")