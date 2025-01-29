
from flask import request
from app.database import row2dict
from flask_restx import Namespace, Resource
from app.api.decorators import role_required
from app.core.lib.sql import SqlSelect, SqlExec

sql_ns = Namespace(name="sql",description="SQL namespace",validate=True)

@sql_ns.route("/select", endpoint="select_query")
class SelectQuery(Resource):
    @role_required('user')
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
    @role_required('admin')
    @sql_ns.param('query', 'SQL execute')
    def get(self):
        '''
        Select SQL
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
