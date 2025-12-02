from flask import render_template, send_from_directory, current_app, session, request, jsonify
from flask_login import current_user
from . import blueprint
from app.configuration import Config
from app.logging_config import getLogger
from app.authentication.handlers import handle_user_required, handle_editor_required
from app.core.lib.common import getModulesByAction
from app.core.lib.object import getObject, getProperty, setProperty, addObjectProperty, getObjectsByClass
from app.core.lib.constants import PropertyType
from app.core.main.ObjectsStorage import objects_storage
import json

_logger = getLogger("main")

@blueprint.route("/admin")
@handle_editor_required
def control_panel():
    old_style = getProperty("SystemVar.control_panel_style") == 'old'
    if old_style:
        widgets = {}
        modules = getModulesByAction("widget")
        for plugin in modules:
            if plugin.config.get('hide_widget',False):
                continue
            try:
                widgets[plugin.name] = plugin.widget()
            except Exception as ex:
                _logger.exception(ex)

        objects = getProperty("SystemVar.control_panel_objects")
        object_render = {}
        if objects:
            for key in objects:
                obj = getObject(key)
                if not obj:
                    continue
                render = obj.render()
                if render:
                    object_render[key] = render


        content = {"widgets":widgets, "objects": object_render}
        return render_template("control_panel.html", **content)

    columns = 12  # default
    if current_user.is_authenticated:
        username = current_user.username
        saved_columns = getProperty(f"{username}.widgets_columns")
        if saved_columns:
            try:
                columns = int(saved_columns)
            except (ValueError, TypeError):
                pass        
    content = {"columns":columns}
    return render_template("control_panel_vue.html", **content)

@blueprint.route("/pages")
@handle_user_required
def pages_panel():
    modules = getModulesByAction("page")
    content = {"modules":modules}
    return render_template("pages_panel.html", **content)

# Маршрут для отображения файлов документации
@blueprint.route('/docs/<path:filename>')
@handle_user_required
def docs_file(filename):
    return send_from_directory(Config.DOCS_DIR, filename)

# About
@blueprint.route("/about")
@handle_user_required
def about():
    content = {
        'LANGUAGES':current_app.config['LANGUAGES']
    }
    return render_template("about.html", **content)

@blueprint.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in current_app.translations:
        session['lang'] = lang
    return 'Ok'

@blueprint.route("/admin/widgets-layout", methods=["GET"])
@handle_editor_required
def get_widgets_layout():
    """Get widgets layout configuration for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        
        username = current_user.username
        # Ensure property exists
        user_obj = getObject(username)
        if user_obj and 'widgets_layout' not in user_obj.properties:
            addObjectProperty('widgets_layout', username, 'Widgets layout configuration', 0, PropertyType.String)
        if user_obj and 'widgets_columns' not in user_obj.properties:
            addObjectProperty('widgets_columns', username, 'Widgets columns configuration', 0, PropertyType.Integer)
        
        layout = getProperty(f"{username}.widgets_layout")
        columns = getProperty(f"{username}.widgets_columns")
        
        layout_data = None
        if layout:
            try:
                layout_data = json.loads(layout) if isinstance(layout, str) else layout
            except json.JSONDecodeError:
                return jsonify({"success": False, "error": "Invalid layout format"}), 400
        
        columns_value = None
        if columns:
            try:
                columns_value = int(columns)
            except (ValueError, TypeError):
                pass
        
        return jsonify({
            "success": True, 
            "layout": layout_data,
            "columns": columns_value
        }), 200
    except Exception as ex:
        _logger.exception(ex)
        return jsonify({"success": False, "error": str(ex)}), 500

@blueprint.route("/admin/widgets-layout", methods=["POST"])
@handle_editor_required
def save_widgets_layout():
    """Save widgets layout configuration for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        
        username = current_user.username
        data = request.get_json()
        
        if data is None:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        layout = data.get("layout")
        columns = data.get("columns", 12)
        
        # Логируем полученные данные для отладки
        _logger.debug("Saving widgets layout for user %s: layout items count = %s, columns = %s", 
                     username, len(layout) if layout else 0, columns)
        if layout:
            for item in layout[:3]:  # Логируем первые 3 элемента для отладки
                _logger.debug("Layout item: id=%s, type=%s, key=%s, settings=%s", 
                             item.get('id'), item.get('type'), item.get('key'), item.get('settings'))
        
        # Ensure property exists
        user_obj = getObject(username)
        if user_obj and 'widgets_layout' not in user_obj.properties:
            addObjectProperty('widgets_layout', username, 'Widgets layout configuration', 0, PropertyType.String)
        if user_obj and 'widgets_columns' not in user_obj.properties:
            addObjectProperty('widgets_columns', username, 'Widgets columns count', 0, PropertyType.String)
        
        # Save layout
        layout_json = json.dumps(layout) if layout else None
        setProperty(f"{username}.widgets_layout", layout_json, source="control_panel")
        setProperty(f"{username}.widgets_columns", columns, source="control_panel")
        
        return jsonify({"success": True}), 200
    except Exception as ex:
        _logger.exception(ex)
        return jsonify({"success": False, "error": str(ex)}), 500

@blueprint.route("/admin/available-widgets", methods=["GET"])
@handle_editor_required
def get_available_widgets():
    """Get list of available widgets (modules and objects)"""
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        
        # Get available modules with widgets
        modules = getModulesByAction("widget")
        available_modules = []
        for plugin in modules:
            if plugin.config.get('hide_widget', False):
                continue
            try:
                # Check if widget can be rendered
                available_modules.append({
                    'key': plugin.name,
                    'title': getattr(plugin, 'title', plugin.name),
                    'description': getattr(plugin, 'description', ''),
                    'category': getattr(plugin, 'category', ''),
                    'widgets': plugin.widgets(),
                    'type': 'module'
                })
            except Exception as ex:
                _logger.exception(ex)
                continue
        
        # Get available objects
        available_objects = []
        for key, obj in sorted(objects_storage.items(), key=lambda x: x[0].lower()):
            try:
                render = obj.render()
                if render:
                    available_objects.append({
                        'key': key,
                        'title': obj.name,
                        'description': obj.description,
                        'category': 'Objects',
                        'type': 'object'
                    })
            except Exception as ex:
                _logger.exception(ex)
                continue
        
        return jsonify({
            "success": True,
            "modules": available_modules,
            "objects": available_objects
        }), 200
    except Exception as ex:
        _logger.exception(ex)
        return jsonify({"success": False, "error": str(ex)}), 500

@blueprint.route("/admin/widget-content", methods=["GET"])
@handle_editor_required
def get_widget_content():
    """Get widget content (HTML) for a specific widget"""
    try:
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "Not authenticated"}), 401
        
        widget_type = request.args.get('type')
        widget_key = request.args.get('key')
        widget_name = request.args.get('widget_name')  # Имя виджета для модулей с несколькими виджетами
        settings_json = request.args.get('settings')
        
        if not widget_type or not widget_key:
            return jsonify({"success": False, "error": "Missing type or key"}), 400
        
        # Парсим настройки, если они переданы
        settings = {}
        if settings_json:
            try:
                settings = json.loads(settings_json)
            except json.JSONDecodeError:
                _logger.warning("Invalid settings JSON for widget %s: %s", widget_key, settings_json)
        
        widget_html = None
        
        if widget_type == 'module':
            modules = getModulesByAction("widget")
            for plugin in modules:
                if plugin.name == widget_key:
                    try:
                        # Передаем имя виджета и настройки в виджет, если метод поддерживает параметры
                        if hasattr(plugin, 'widget') and callable(plugin.widget):
                            import inspect
                            sig = inspect.signature(plugin.widget)
                            params = list(sig.parameters.keys())
                            
                            # Если метод принимает name как первый параметр
                            if len(params) > 0 and params[0] == 'name':
                                if widget_name:
                                    widget_html = plugin.widget(widget_name)
                                else:
                                    widget_html = plugin.widget(None)
                            # Если метод принимает name и settings
                            elif len(params) > 1:
                                if 'name' in params and 'settings' in params:
                                    widget_html = plugin.widget(name=widget_name, settings=settings)
                                elif 'name' in params:
                                    widget_html = plugin.widget(name=widget_name)
                                elif 'settings' in params:
                                    widget_html = plugin.widget(settings=settings)
                                else:
                                    widget_html = plugin.widget()
                            # Если метод принимает только settings
                            elif len(params) > 0 and 'settings' in params:
                                widget_html = plugin.widget(settings=settings)
                            # Если метод не принимает параметры
                            else:
                                widget_html = plugin.widget()
                        else:
                            widget_html = plugin.widget()
                        break
                    except Exception as ex:
                        _logger.exception(ex)
                        return jsonify({"success": False, "error": str(ex)}), 500
        elif widget_type == 'object':
            obj = getObject(widget_key)
            if obj:
                try:
                    # Передаем настройки в render, если метод поддерживает параметры
                    if hasattr(obj, 'render') and callable(obj.render):
                        import inspect
                        sig = inspect.signature(obj.render)
                        if len(sig.parameters) > 0:
                            widget_html = obj.render(settings=settings)
                        else:
                            widget_html = obj.render()
                    else:
                        widget_html = obj.render()
                except Exception as ex:
                    _logger.exception(ex)
                    return jsonify({"success": False, "error": str(ex)}), 500
        
        if widget_html:
            return jsonify({
                "success": True,
                "html": widget_html
            }), 200
        else:
            return jsonify({"success": False, "error": "Widget not found"}), 404
            
    except Exception as ex:
        _logger.exception(ex)
        return jsonify({"success": False, "error": str(ex)}), 500
