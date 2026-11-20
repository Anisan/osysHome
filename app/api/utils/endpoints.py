from flask import request, jsonify, current_app, g
from flask_restx import Namespace, Resource, fields
from sqlalchemy import func, case
from app.core.models.Plugins import Notify
from app.api.decorators import api_key_required
from app.api.models import (
    model_analytics_get,
    model_analytics_set,
    model_cron_validate_response,
    model_error_message,
    model_error_msg,
    model_error_rate_mute_list,
    model_intelli_response,
    model_lsp_response,
    model_mute_created,
    model_notification_stats_response,
    model_notifications_response,
    model_run_code_response,
    model_search_response,
    model_success,
    model_validate_python_error,
)
from app.authentication.handlers import handle_admin_required, handle_user_required
from app.logging_config import getLogger
from app.extensions import cache
from app.database import session_scope
from app.core.lsp_client import run_lsp_action
from app.core.lib.execute import compile_method_code

_logger = getLogger("api")

utils_ns = Namespace(
    name="utils",
    description="Search, notifications, code tools, cron and analytics utilities",
    validate=True,
)

response_success = utils_ns.model('Success', model_success)
response_error_msg = utils_ns.model('ErrorMsg', model_error_msg)
response_error_message = utils_ns.model('ErrorMessage', model_error_message)
response_search = utils_ns.model('SearchResponse', model_search_response)
response_mute_list = utils_ns.model('ErrorRateMuteList', model_error_rate_mute_list)
response_mute_created = utils_ns.model('ErrorRateMuteCreated', model_mute_created)
validate_python_error = utils_ns.model('ValidatePythonError', model_validate_python_error)
response_intelli = utils_ns.model('IntelliResponse', model_intelli_response)
response_lsp = utils_ns.model('LspResponse', model_lsp_response)
response_run = utils_ns.model('RunCodeResponse', model_run_code_response)
response_cron_validate = utils_ns.model('CronValidateResponse', model_cron_validate_response)
response_notifications = utils_ns.model('NotificationsResponse', model_notifications_response)
response_notification_stats = utils_ns.model(
    'NotificationStatsResponse', model_notification_stats_response
)
response_analytics_get = utils_ns.model('AnalyticsGet', model_analytics_get)
response_analytics_set = utils_ns.model('AnalyticsSet', model_analytics_set)


@utils_ns.route("/search")
class GlobalSearch(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Global plugin search with cache and limits")
    @utils_ns.param("query", "A query string parameter")
    @utils_ns.param("limit", "Maximum number of results (default: 50)")
    @utils_ns.response(200, "Search results.", response_search)
    @utils_ns.response(400, "Query too short.", response_error_msg)
    def get(self):
        """
        Global search with caching and limits
        """
        query = request.args.get("query", None)
        limit = int(request.args.get("limit", 50))

        if not query or len(query) <= 2:
            return {"success": False, "msg": "Query too short"}, 400

        # Кэширование результатов поиска
        cache_key = f"search:v2:{query}:{limit}"
        cached_result = cache.get(cache_key)

        if cached_result:
            if isinstance(cached_result, dict):
                items = cached_result.get("items", [])
                errors = cached_result.get("errors", [])
                return {
                    "success": True,
                    "items": items,
                    "count": len(items),
                    "errors": errors,
                }, 200
            if isinstance(cached_result, list):
                # Backward compatibility with earlier JSON-only cache.
                return {"success": True, "items": cached_result, "count": len(cached_result), "errors": []}, 200
            # Backward compatibility for short-lived cache entries created by older HTML response format.
            cache.delete(cache_key)

        result = []
        module_errors = []
        from app.core.lib.common import getModulesByAction

        plugins = getModulesByAction("search")
        for plugin in plugins:
            plugin_name = getattr(plugin, "title", None) or getattr(plugin, "name", None)
            if not plugin_name:
                try:
                    plugin_name = plugin["name"]
                except Exception:
                    plugin_name = plugin.__class__.__name__
            try:
                res = plugin.search(query)
                if res is None:
                    continue
                if not isinstance(res, list):
                    raise TypeError("search() must return list")

                valid_items = [item for item in res if isinstance(item, dict)]
                result.extend(valid_items[:limit])  # Ограничиваем результаты

                if len(result) >= limit:
                    result = result[:limit]
                    break

            except Exception as ex:
                _logger.exception(ex)
                module_errors.append(
                    {
                        "module": plugin_name,
                        "error": str(ex),
                    }
                )

        normalized_items = []
        for item in result[:limit]:
            if not isinstance(item, dict):
                continue
            normalized_items.append(
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "tags": item.get("tags", []),
                }
            )

        payload = {"items": normalized_items, "errors": module_errors}

        # Кэшируем на 2 минуты
        cache.set(cache_key, payload, timeout=120)

        return {
            "success": True,
            "items": normalized_items,
            "count": len(normalized_items),
            "errors": module_errors,
        }, 200


@utils_ns.route("/readnotify/<int:id>")
class ReadNotify(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Mark a notification as read")
    @utils_ns.response(200, "Marked as read.", response_success)
    def get(self, id):
        """
        Mark read notify
        """
        from app.core.lib.common import readNotify

        readNotify(id)
        return {"success": True}, 200


@utils_ns.route("/notify/<int:id>")
class DeleteNotify(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Delete a notification by id")
    @utils_ns.response(200, "Deleted.", response_success)
    @utils_ns.response(404, "Not Found", response_error_message)
    def delete(self, id):
        """
        Delete notify by id
        """
        from app.core.lib.common import deleteNotify

        result = deleteNotify(id)
        if not result:
            return {"success": False, "message": "Notify not found"}, 404
        return {"success": True}, 200


@utils_ns.route("/readnotify/all")
class ReadNotifyAll(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Mark all matching notifications as read")
    @utils_ns.param("source", "Source notify (optional, if not provided marks all notifications as read)")
    @utils_ns.param(
        "control_panel",
        "If true, mark as read all notifications whose source is not a system module",
    )
    @utils_ns.response(200, "Marked as read.", response_success)
    def get(self):
        """
        Mark read all notify for source. If source is not provided, marks all notifications as read.
        """
        source = request.args.get("source", None)
        control_panel = str(request.args.get("control_panel", "false")).lower() in ("true", "1", "yes")
        from app.core.lib.common import readNotifyAll

        readNotifyAll(source, control_panel=control_panel)
        return {"success": True}, 200


@utils_ns.route("/error-rate-mute")
class ErrorRateMuteList(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="List muted error-rate fingerprints")
    @utils_ns.response(200, "Mute list.", response_mute_list)
    def get(self):
        """Список заглушенных error-rate fingerprint (mute_id)."""
        from app.logging_config import list_error_rate_mutes

        items = list_error_rate_mutes()
        return {"success": True, "items": items, "count": len(items)}, 200

    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Remove error-rate mute by mute_id")
    @utils_ns.param("mute_id", "Mute id (sha256 of fingerprint)")
    @utils_ns.response(200, "Unmuted.", response_success)
    @utils_ns.response(400, "Bad Request", response_error_message)
    @utils_ns.response(404, "Not Found", response_error_message)
    def delete(self):
        """Снять mute по mute_id (query или JSON body)."""
        from app.logging_config import unmute_error_rate

        mute_id = request.args.get("mute_id")
        if not mute_id and request.is_json:
            mute_id = (request.get_json(silent=True) or {}).get("mute_id")
        if not mute_id:
            return {"success": False, "message": "mute_id required"}, 400
        removed = unmute_error_rate(str(mute_id))
        if not removed:
            return {"success": False, "message": "Mute not found"}, 404
        return {"success": True}, 200


@utils_ns.route("/error-rate-mute/<int:notify_id>")
class ErrorRateMuteFromNotify(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Mute error-rate from notify card and mark read")
    @utils_ns.response(200, "Muted.", response_mute_created)
    @utils_ns.response(400, "Bad Request", response_error_message)
    @utils_ns.response(404, "Not Found", response_error_message)
    def post(self, notify_id):
        """Mute по карточке notify (kind=error_rate) и отметить прочитанным."""
        import json
        from app.core.lib.common import readNotify
        from app.logging_config import (
            _ERROR_RATE_NOTIFY_KIND,
            _ERROR_RATE_NOTIFY_SOURCE,
            _mute_id_from_fingerprint,
            mute_error_rate,
        )

        with session_scope() as session:
            row = session.query(Notify).filter(Notify.id == notify_id).one_or_none()
            if row is None:
                return {"success": False, "message": "Notify not found"}, 404
            if row.source != _ERROR_RATE_NOTIFY_SOURCE:
                return {"success": False, "message": "Not an error-rate notify"}, 400

            params = {}
            if row.params:
                try:
                    parsed = json.loads(row.params) if isinstance(row.params, str) else row.params
                    if isinstance(parsed, dict):
                        params = parsed
                except Exception:
                    params = {}

            if params.get("kind") != _ERROR_RATE_NOTIFY_KIND:
                return {"success": False, "message": "Not an error-rate notify"}, 400

            logger_name = params.get("logger") or ""
            message = row.description or ""
            mute_id = params.get("mute_id")
            if not mute_id and logger_name:
                mute_id = _mute_id_from_fingerprint(f"{logger_name}\0{message}")
            if not mute_id:
                return {"success": False, "message": "mute_id missing"}, 400

        mute_error_rate(str(mute_id), logger_name=str(logger_name), message=str(message))
        readNotify(notify_id)
        return {"success": True, "mute_id": mute_id}, 200


@utils_ns.route("/validate-python")
class ValidateCode(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Validate Python method/task code syntax")
    @utils_ns.expect(utils_ns.model('ValidatePythonBody', {
        'code': fields.String(required=True, description='Python code to validate'),
    }))
    @utils_ns.response(200, "List of syntax errors (empty if ok).", [validate_python_error])
    def post(self):
        code = request.json.get('code', '')
        errors = []

        try:
            # Same path as method/task runtime: top-level return is allowed.
            compile_method_code(code, "<editor>")
        except SyntaxError as e:
            errors.append({
                "row": e.lineno - 1,          # Ace использует 0-based индекс
                "column": e.offset - 1 if e.offset else 0,
                "text": str(e.msg),
                "type": "error"
            })
        except Exception as e:
            # Другие ошибки (например, неожиданный EOF)
            errors.append({
                "row": max(0, len(code.splitlines()) - 1),
                "column": 0,
                "text": str(e),
                "type": "error"
            })

        return jsonify(errors)

@utils_ns.route("/intelli-python")
class IntelliPython(Resource):
    @api_key_required
    @handle_user_required
    @utils_ns.doc(security="apikey", description="IntelliSense symbol cache for Python editor")
    @utils_ns.response(200, "Symbol list.", response_intelli)
    def get(self):
        cache = list(current_app.extensions.get('intelli_cache', []))
        try:
            from app.core.main.CustomFunctionRegistry import custom_function_registry
            cache.extend(custom_function_registry.get_intelli_cache())
        except Exception:
            pass
        return {"symbols": cache}


lsp_request_model = utils_ns.model(
    "LspPythonRequest",
    {
        "action": fields.String(required=True, description="completion | hover | diagnostics | signature"),
        "code": fields.String(required=True, description="Python code to analyze"),
        "line": fields.Integer(required=False, description="1-based line number for position-based actions"),
        "column": fields.Integer(required=False, description="0-based column number for position-based actions"),
        "object_name": fields.String(required=False, description="Object name for self binding"),
        "module_name": fields.String(required=False, description="Module path for self type (e.g., 'plugins.TelegramBot')"),
        "exclude_custom_function": fields.String(
            required=False,
            description="CustomFunction name to omit from LSP prelude (editor for that CF)",
        ),
    },
)


@utils_ns.route("/lsp/python")
class LspPython(Resource):
    @api_key_required
    @handle_user_required
    @utils_ns.expect(lsp_request_model, validate=False)
    @utils_ns.doc(security="apikey", description="Python LSP bridge")
    @utils_ns.response(200, "LSP action result.", response_lsp)
    @utils_ns.response(400, "Bad Request", response_lsp)
    def post(self):
        """
        Python LSP bridge (completion / hover / diagnostics / signature)
        """
        payload = request.get_json(force=True, silent=True) or {}
        action = payload.get("action")
        code = payload.get("code", "")
        line = payload.get("line")
        column = payload.get("column")
        object_name = payload.get("object_name")
        module_name = payload.get("module_name")
        exclude_custom_function = payload.get("exclude_custom_function")

        if not action:
            return {"success": False, "error": "Action is required"}, 400

        try:
            result = run_lsp_action(
                action,
                code,
                line=line,
                column=column,
                object_name=object_name,
                module_name=module_name,
                exclude_custom_function=exclude_custom_function,
            )
            result["success"] = True
            return result, 200
        except Exception as ex:
            _logger.exception(ex)
            return {"success": False, "error": str(ex)}, 400


run_model = utils_ns.model(
    "CodeTextModel", {"code": fields.String(description="Python code", required=True)}
)

@utils_ns.route("/run")
class RunCode(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.expect(run_model, validate=True)
    @utils_ns.doc(security="apikey", description="Execute Python code on the server")
    @utils_ns.response(200, "Execution result.", response_run)
    def post(self):
        """
        Run code
        """
        try:
            payload = request.get_json()
            code = payload["code"]
            from app.core.lib.common import runCode

            user = getattr(g, "current_user", None)
            username = getattr(user, "username", None) if user else None
            execution_source = f"api:{username}" if username else "api"
            result, success = runCode(code, execution_source=execution_source)
            return {"success": success, "result": result}, 200
        except Exception as ex:
            return {"success": False, "result": ex}, 200


cron_task_model = utils_ns.model(
    "CodeTextModel",
    {
        "method": fields.String(description="Object method", required=True),
        "crontab": fields.String(description="Crontab", required=True),
    },
)


@utils_ns.route("/crontask")
class setCronTask(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.expect(cron_task_model, validate=True)
    @utils_ns.doc(security="apikey", description="Create or clear periodic cron job for object.method")
    @utils_ns.response(200, "Cron task updated.", response_success)
    def post(self):
        """
        Set cron task for method
        """
        payload = request.get_json()
        obj = payload["method"].split(".")[0]
        method = payload["method"].split(".")[1]
        crontab = payload["crontab"]

        from app.core.lib.common import addCronJob, clearScheduledJob

        clearScheduledJob(f"{obj}_{method}_periodic")
        if crontab:
            addCronJob(
                f"{obj}_{method}_periodic",
                f'callMethod("{obj}.{method}", source="Scheduler")',
                crontab,
            )

        return {"success": True}, 200


cron_validate_model = utils_ns.model(
    "CronValidateModel",
    {
        "crontab": fields.String(description="Cron expression", required=True),
        "count": fields.Integer(description="Number of next runs to preview (1-10)", required=False),
    },
)


@utils_ns.route("/cron/validate")
class ValidateCron(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.expect(cron_validate_model, validate=True)
    @utils_ns.doc(security="apikey", description="Validate cron expression and preview next runs")
    @utils_ns.response(200, "Validation result.", response_cron_validate)
    def post(self):
        """Validate cron expression and return upcoming run times (server timezone)."""
        payload = request.get_json() or {}
        crontab = payload.get("crontab", "")
        count = payload.get("count", 5)
        from app.core.lib.crontab import validate_cron_expression

        result = validate_cron_expression(crontab, preview_count=count)
        tz = result.get("timezone")
        if tz is not None:
            result["timezone"] = str(tz)
        result["success"] = bool(result.get("ok"))
        return result, 200


@utils_ns.route("/notifications")
class GetNotifications(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="List notifications with filters")
    @utils_ns.param("source", "Filter by source (optional)")
    @utils_ns.param("unread_only", "Show only unread notifications (default: true)")
    @utils_ns.param(
        "control_panel",
        "If true, return notifications whose source is not a system module "
        "(admin page: admin/osysHome/orphans). Ignores source filter.",
    )
    @utils_ns.response(200, "Notifications list.", response_notifications)
    def get(self):
        """
        Get notifications with filtering options
        """
        source = request.args.get("source", None)
        unread_only = request.args.get("unread_only", "true").lower() == "true"
        control_panel = str(request.args.get("control_panel", "false")).lower() in ("true", "1", "yes")

        query = Notify.query

        if control_panel:
            from app.core.lib.common import getPluginModuleNames
            from sqlalchemy import or_

            module_names = list(getPluginModuleNames())
            if module_names:
                query = query.filter(
                    or_(
                        Notify.source.is_(None),
                        Notify.source == "",
                        Notify.source.notin_(module_names),
                    )
                )
            else:
                query = query.filter(
                    or_(
                        Notify.source.is_(None),
                        Notify.source == "",
                        Notify.source.in_(["admin", "osysHome", "core"]),
                    )
                )
        elif source:
            query = query.filter(Notify.source == source)

        if unread_only:
            query = query.filter(Notify.read == False)  # noqa

        notifications = query.order_by(Notify.created.desc()).all()

        from app.core.lib.common import notify_to_dict

        result = []
        for item in notifications:
            result.append(notify_to_dict(item))

        return {"success": True, "notifications": result}, 200


@utils_ns.route("/notifications/stats")
class NotificationStats(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Notification counts by source")
    @utils_ns.response(200, "Notification statistics.", response_notification_stats)
    def get(self):
        """
        Get notification statistics
        """
        with session_scope() as session:
            total = session.query(Notify).count()
            unread = session.query(Notify).filter(Notify.read == False).count()  # noqa

            # Статистика по источникам
            source_stats = (
                session.query(
                    Notify.source,
                    func.count(Notify.id).label("total"),
                    func.sum(case((Notify.read == False, 1), else_=0)).label("unread"),  # noqa
                )
                .group_by(Notify.source)
                .all()
            )

            sources = []
            for stat in source_stats:
                sources.append(
                    {"source": stat.source, "total": stat.total, "unread": stat.unread}
                )

            return {
                "success": True,
                "stats": {"total": total, "unread": unread, "sources": sources},
            }, 200


@utils_ns.route("/analytics")
class AnalyticsSettings(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Get analytics opt-in status")
    @utils_ns.response(200, "Analytics settings.", response_analytics_get)
    def get(self):
        """
        Get analytics opt-in status. Enum: disabled, basic, extended. null/empty = not asked.
        """
        from app.core.lib.object import getProperty

        val = getProperty("SystemVar.analytics_enabled")
        # Legacy: "true"/"false" -> map to basic/disabled
        if str(val).lower() in ("true", "1", "yes"):
            val = "basic"
        elif str(val).lower() in ("false", "0", "no"):
            val = "disabled"
        return {
            "success": True,
            "analytics_enabled": val,
            "asked": val not in (None, ""),
        }, 200

    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey", description="Set analytics level (explicit consent)")
    @utils_ns.param("enabled", "disabled | basic | extended", _in="query", required=True)
    @utils_ns.response(200, "Analytics updated.", response_analytics_set)
    @utils_ns.response(400, "Bad Request", response_error_msg)
    def post(self):
        """
        Set analytics level (explicit consent). disabled, basic, extended.
        """
        from app.core.lib.object import setProperty

        enabled = request.args.get("enabled", "").lower()
        if enabled not in ("disabled", "basic", "extended"):
            return {"success": False, "msg": "enabled must be disabled, basic or extended"}, 400
        setProperty("SystemVar.analytics_enabled", enabled, "api")
        return {"success": True, "analytics_enabled": enabled}, 200
