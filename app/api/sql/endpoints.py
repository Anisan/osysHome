
from flask import request
from app.database import row2dict
from flask_restx import Namespace, Resource, fields
from app.authentication.handlers import handle_user_required, handle_admin_required
from app.core.lib.sql import SqlSelect, SqlExec, SqlInsert, SqlUpdate

sql_ns = Namespace(name="sql",description="SQL namespace",validate=True)

@sql_ns.route("/select", endpoint="select_query")
class SelectQuery(Resource):
    @handle_user_required
    @sql_ns.param('query', 'SQL query')
    def get(self):
        '''
        Select SQL
        '''
        query = request.args.get("query",None)
        if query:
            data = []
            result = SqlSelect(query)
            for row in result:
                data.append(dict(row))
            return {
                'success': True,
                'result': data}, 200
        return {
            'success': False,
            'message': 'Query is empty'}, 404
    
@sql_ns.route("/exec", endpoint="exec_query")
class ExecQuery(Resource):
    @handle_admin_required
    @sql_ns.param('query', 'SQL execute')
    def get(self):
        '''
        Execute SQL
        '''
        query = request.args.get("query",None)
        if query:
            try:
                SqlExec(query)
                return {'success': True}, 200
            except Exception as ex:
                return {'success': False, 'error': str(ex)}, 200
        return {
            'success': False,
            'message': 'Query is empty'}, 404


insert_model = sql_ns.model('InsertModel', {
    'table': fields.String(required=True, description='The table name'),
    'data': fields.Raw(required=True, description='The data (dictionary - column:value)'),
})

@sql_ns.route("/insert", endpoint="insert_query")
class InsertQuery(Resource):
    @handle_user_required
    @sql_ns.expect(insert_model)
    def post(self):
        '''
        Insert model
        '''
        model = sql_ns.payload
        try:
            res = SqlInsert(model['table'], model['data'])
            return {'success': res}, 200
        except Exception as ex:
            return {'success': False, 'error': str(ex)}, 200


update_model = sql_ns.model('UpdateModel', {
    'table': fields.String(required=True, description='The table name'),
    'data': fields.Raw(required=True, description='The data (dictionary - column:value)'),
    'id_column': fields.String(required=True, description='The column name for identification')
})

@sql_ns.route("/update", endpoint="update_query")
class UpdateQuery(Resource):
    @handle_user_required
    @sql_ns.expect(update_model)
    def post(self):
        '''
        Update model
        '''
        model = sql_ns.payload
        try:
            res = SqlUpdate(model['table'], model['data'],model['id_column'])
            return {'success': res}, 200
        except Exception as ex:
            return {'success': False, 'error': str(ex)}, 200

