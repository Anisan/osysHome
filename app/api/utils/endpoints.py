from flask import request, render_template
from flask_restx import Namespace, Resource, fields
from sqlalchemy import func, case
from app.core.models.Plugins import Notify
from app.api.decorators import api_key_required
from app.authentication.handlers import handle_admin_required
from app.logging_config import getLogger
from app.extensions import cache
from app.database import session_scope

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
        cache_key = f"search:{query}:{limit}"
        cached_result = cache.get(cache_key)

        if cached_result:
            return {"success": True, "result": cached_result}, 200

        result = []
        from app.core.lib.common import getModulesByAction

        plugins = getModulesByAction("search")
        for plugin in plugins:
            try:
                res = plugin.search(query)
                result.extend(res[:limit])  # Ограничиваем результаты

                if len(result) >= limit:
                    result = result[:limit]
                    break

            except Exception as ex:
                _logger.exception(ex)
                name = plugin["name"]
                result.append(
                    {
                        "url": "Logs",
                        "title": f"{ex}",
                        "tags": [{"name": name, "color": "danger"}],
                    }
                )

        render = render_template("search_result.html", result=result)

        # Кэшируем на 2 минуты
        cache.set(cache_key, render, timeout=120)

        return {"success": True, "result": render}, 200


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
    @utils_ns.param("source", "Source notify")
    def get(self):
        """
        Mark read all notify for source
        """
        source = request.args.get("source", None)
        if not source:
            return {"success": False, "msg": "Need source"}, 404
        from app.core.lib.common import readNotifyAll

        readNotifyAll(source)
        return {"success": True}, 200


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
            query = query.filter(not Notify.read)

        notifications = query.order_by(Notify.created.desc()).all()

        result = []
        for notification in notifications:
            result.append(
                {
                    "id": notification.id,
                    "name": notification.name,
                    "description": notification.description,
                    "category": (
                        notification.category.value if notification.category else "Info"
                    ),
                    "source": notification.source,
                    "created": (
                        notification.created.isoformat()
                        if notification.created
                        else None
                    ),
                    "read": notification.read,
                    "count": notification.count,
                }
            )

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
            unread = session.query(Notify).filter(Notify.read == False).count()  # Исправлено условие # noqa

            # Статистика по источникам
            source_stats = (
                session.query(  # Исправлено: используем session.query вместо Notify.query
                    Notify.source,
                    func.count(Notify.id).label("total"),
                    func.sum(case((Notify.read == False, 1), else_=0)).label("unread"),  # Исправлено подсчет непрочитанных # noqa
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
