"""API blueprint configuration."""
from app.utils import get_current_version
from flask import Blueprint, render_template
from flask_restx import Api, Resource
from werkzeug.exceptions import HTTPException
from app.logging_config import getLogger
from app.api.decorators import g, api_key_required
from app.authentication.handlers import public_endpoint
from app.api.models import model_about, model_user_result
from app.api.classes.endpoints import classes_ns
from app.api.objects.endpoints import objects_ns
from app.api.properties.endpoints import props_ns
from app.api.methods.endpoints import methods_ns
from app.api.utils.endpoints import utils_ns
from app.api.export.endpoints import export_ns
from app.api.import_.endpoints import import_ns
from app.api.sql.endpoints import sql_ns
from app.api.plugins.endpoints import plugins_ns
from app.api.custom_functions.endpoints import custom_functions_ns

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

_API_DESCRIPTION = """
osysHome REST API for objects, properties, methods, plugins and admin utilities.

## Getting started

- **Public info:** [`GET /api/about`](/api/about) (no key required)
- **Current user:** [`GET /api/user`](/api/user)

## Authentication

Most endpoints require an API key. Pass it as a query parameter:

```
?apikey=YOUR_KEY
```

Authorize in Swagger UI with the **apikey** button (top right), then try requests.
"""

api = Api(
    api_blueprint,
    version=get_current_version(),
    title="osysHome API",
    description=_API_DESCRIPTION,
    doc="/",
    authorizations=authorizations,
    security='apikey',
    contact="Eraser",
    contact_email="eraser1981@gmail.com",
    contact_url="https://github.com/Anisan/osysHome",
    license="Hobbyist License v1.0",
    license_url="https://github.com/Anisan/osysHome/blob/master/LICENSE",
)

_URL_NOT_FOUND_PREFIX = "The requested URL was not found"


def _normalize_404_msg(description) -> str:
    """Короткий msg вместо длинного текста Werkzeug/flask-restx."""
    if not description:
        return "Not Found"
    text = str(description)
    if text.startswith(_URL_NOT_FOUND_PREFIX):
        return "Not Found"
    return text


_original_handle_error = api.handle_error


def _handle_error(e):
    """Единый JSON 404: {success: false, msg} вместо {message} от flask-restx."""
    if isinstance(e, HTTPException) and e.code == 404:
        return api.make_response(
            {"success": False, "msg": _normalize_404_msg(e.description)},
            404,
        )
    return _original_handle_error(e)


api.handle_error = _handle_error


def _render_swagger_doc():
    """Кастомная страница Swagger с логотипом osysHome."""
    return render_template(
        "api/swagger_ui.html",
        title=api.title,
        specs_url=api.specs_url,
    )


# _doc_view вызывается из render_doc (url rule уже зарегистрирован в Api.__init__)
api._doc_view = _render_swagger_doc

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

about_model = api.model('About', model_about)
user_model = api.model('CurrentUser', model_user_result)


@api.route('/about')
class AboutResource(Resource):
    @public_endpoint
    @api.doc(security=None, description='Public application info')
    @api.response(200, 'About information.', about_model)
    def get(self):
        '''
        Get about information (name, author, version, email).
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
    @api.response(200, 'Current user.', user_model)
    def get(self):
        '''
        Get current authenticated user information.
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
api.add_namespace(custom_functions_ns, path="/custom-functions")
