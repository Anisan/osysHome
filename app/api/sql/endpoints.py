
from flask import request
from flask_restx import Namespace, Resource, fields
from app.authentication.handlers import handle_admin_required
from app.core.lib.sql import SqlSelect, SqlExec, SqlInsert, SqlUpdate
from app.api.models import (
    model_error_message,
    model_sql_exec_response,
    model_sql_mutate_response,
    model_sql_select_response,
)

sql_ns = Namespace(
    name="sql",
    description="Admin SQL select / exec / insert / update helpers",
    validate=True,
)

response_select = sql_ns.model('SqlSelectResponse', model_sql_select_response)
response_exec = sql_ns.model('SqlExecResponse', model_sql_exec_response)
response_mutate = sql_ns.model('SqlMutateResponse', model_sql_mutate_response)
response_empty = sql_ns.model('SqlEmptyQuery', model_error_message)

insert_model = sql_ns.model('InsertModel', {
    'table': fields.String(required=True, description='The table name'),
    'data': fields.Raw(required=True, description='The data (dictionary - column:value)'),
})

update_model = sql_ns.model('UpdateModel', {
    'table': fields.String(required=True, description='The table name'),
    'data': fields.Raw(required=True, description='The data (dictionary - column:value)'),
    'id_column': fields.String(required=True, description='The column name for identification'),
})


@sql_ns.route("/select", endpoint="select_query")
class SelectQuery(Resource):
    @handle_admin_required
    @sql_ns.doc(description="Execute SELECT and return rows as dictionaries")
    @sql_ns.param('query', 'SQL query')
    @sql_ns.response(200, "Query rows.", response_select)
    @sql_ns.response(404, "Empty query.", response_empty)
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
    @sql_ns.doc(description="Execute SQL statement (DDL/DML without result set)")
    @sql_ns.param('query', 'SQL execute')
    @sql_ns.response(200, "Execution result.", response_exec)
    @sql_ns.response(404, "Empty query.", response_empty)
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


@sql_ns.route("/insert", endpoint="insert_query")
class InsertQuery(Resource):
    @handle_admin_required
    @sql_ns.expect(insert_model)
    @sql_ns.doc(description="Insert a row into a table")
    @sql_ns.response(200, "Insert result.", response_mutate)
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


@sql_ns.route("/update", endpoint="update_query")
class UpdateQuery(Resource):
    @handle_admin_required
    @sql_ns.expect(update_model)
    @sql_ns.doc(description="Update a row identified by id_column")
    @sql_ns.response(200, "Update result.", response_mutate)
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
