from flask import request, jsonify, current_app
import ast
from flask_restx import Namespace, Resource, fields
from sqlalchemy import func, case
from app.core.models.Plugins import Notify
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required, handle_user_required
from app.logging_config import getLogger
from app.extensions import cache
from app.database import row2dict, session_scope
from app.core.lsp_client import run_lsp_action

_logger = getLogger("api")

utils_ns = Namespace(name="utils", description="Utilites namespace", validate=True)


@utils_ns.route("/search")
class GlobalSearch(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
    @utils_ns.param("query", "A query string parameter")
    @utils_ns.param("limit", "Maximum number of results (default: 50)")
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


@utils_ns.route("/readnotify/<id>")
class ReadNotify(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
    def get(self, id):
        """
        Mark read notify
        """
        from app.core.lib.common import readNotify

        readNotify(id)
        return {"success": True}, 200


@utils_ns.route("/readnotify/all")
class ReadNotifyAll(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
    @utils_ns.param("source", "Source notify (optional, if not provided marks all notifications as read)")
    def get(self):
        """
        Mark read all notify for source. If source is not provided, marks all notifications as read.
        """
        source = request.args.get("source", None)
        from app.core.lib.common import readNotifyAll

        readNotifyAll(source)
        return {"success": True}, 200

@utils_ns.route("/validate-python")
class ValidateCode(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
    def post(self):
        code = request.json.get('code', '')
        errors = []

        try:
            ast.parse(code, filename="<editor>")
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
    @utils_ns.doc(security="apikey")
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
    @utils_ns.doc(security="apikey")
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
    @utils_ns.doc(security="apikey")
    def post(self):
        """
        Run code
        """
        try:
            payload = request.get_json()
            code = payload["code"]
            from app.core.lib.common import runCode

            result, success = runCode(code)
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
    @utils_ns.doc(security="apikey")
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


@utils_ns.route("/notifications")
class GetNotifications(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
    @utils_ns.param("source", "Filter by source (optional)")
    @utils_ns.param("unread_only", "Show only unread notifications (default: true)")
    def get(self):
        """
        Get notifications with filtering options
        """
        source = request.args.get("source", None)
        unread_only = request.args.get("unread_only", "true").lower() == "true"

        query = Notify.query

        if source:
            query = query.filter(Notify.source == source)

        if unread_only:
            query = query.filter(Notify.read == False)  # noqa

        notifications = query.order_by(Notify.created.desc()).all()

        result = []
        for item in notifications:
            item.category = item.category.name if item.category else "Info"
            notification = row2dict(item)
            result.append(notification)

        return {"success": True, "notifications": result}, 200


@utils_ns.route("/notifications/stats")
class NotificationStats(Resource):
    @api_key_required
    @handle_admin_required
    @utils_ns.doc(security="apikey")
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
    @utils_ns.doc(security="apikey")
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
    @utils_ns.doc(security="apikey")
    @utils_ns.param("enabled", "disabled | basic | extended", _in="query", required=True)
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
