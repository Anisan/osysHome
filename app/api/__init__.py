"""API blueprint configuration."""
from app.utils import get_current_version
from flask import Blueprint
from flask_restx import Api, Resource
from app.logging_config import getLogger
from app.api.decorators import g, api_key_required
from app.api.classes.endpoints import classes_ns
from app.api.objects.endpoints import objects_ns
from app.api.properties.endpoints import props_ns
from app.api.methods.endpoints import methods_ns
from app.api.utils.endpoints import utils_ns
from app.api.export.endpoints import export_ns
from app.api.import_.endpoints import import_ns
from app.api.sql.endpoints import sql_ns
from app.api.plugins.endpoints import plugins_ns

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

# Override JSON representation to avoid passing unsupported kwargs (e.g., cls) to dumps
from flask import current_app, make_response


def _safe_output_json(data, code, headers=None):
    dumped = current_app.json.dumps(data)
    resp = make_response(dumped, code)
    resp.headers["Content-Type"] = "application/json"
    if headers:
        resp.headers.extend(headers)
    return resp


api.representations["application/json"] = _safe_output_json

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
            'version': get_current_version(),
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


api.add_namespace(classes_ns, path="/class")
api.add_namespace(objects_ns, path="/object")
api.add_namespace(props_ns, path="/property")
api.add_namespace(methods_ns, path="/method")
api.add_namespace(utils_ns, path="/utils")
api.add_namespace(export_ns, path="/export")
api.add_namespace(import_ns, path="/import")
api.add_namespace(sql_ns, path="/sql")
api.add_namespace(plugins_ns, path="/plugins")
