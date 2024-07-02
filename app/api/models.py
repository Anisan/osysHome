from flask_restx import fields

model_404 = {
    'success': fields.Boolean(description='Indicates success of the operation', default=False),
    'msg': fields.String(description='Error message')
}

model_result = {
    'success': fields.Boolean(description='Indicates success of the operation'),
    'result': fields.Raw(description='Result request'),
}