"""Base class plugin"""

import os
import json
from threading import Thread, Event
from flask import Blueprint, request, render_template
from settings import Config
from app.core.models.Plugins import Plugin
from app.core.lib.common import sendDataToWebsocket
from app.database import session_scope, get_now_to_utc
from app.authentication.handlers import handle_admin_required
from app.logging_config import getLogger


class BasePlugin:
    """
    Base class for all osysHome plugins providing core functionality for plugin lifecycle management.

    This abstract base class handles Flask blueprint registration, threading for background tasks,
    configuration management, and standard plugin lifecycle operations. All plugins must inherit
    from this class and implement the required abstract methods.

    The BasePlugin automatically:
    - Creates and registers a Flask Blueprint with proper static/template directories
    - Discovers and registers route methods (methods starting with 'route_')
    - Manages plugin configuration loading/saving from database
    - Provides threading support for cyclic background tasks
    - Handles logging with configurable levels
    - Integrates with the WebSocket system for real-time communication

    Attributes:
        name (str): Unique plugin identifier, set during initialization
        title (str): Human-readable plugin title for UI display
        description (str): Plugin description text
        category (str): Plugin category for UI grouping
        author (str): Plugin author name
        version (int): Plugin version number
        system (bool): Whether this is a system plugin
        actions (list): List of supported actions (e.g., ['cycle', 'proxy'])
        config (dict): Plugin configuration dictionary loaded from database
        thread (Thread): Background thread for cyclic tasks (if applicable)
        event (Event): Threading event for stopping cyclic tasks
        logger (Logger): Plugin-specific logger instance
        blueprint (Blueprint): Flask blueprint for web routes

    Abstract Methods:
        initialization(): Called during plugin startup, must be implemented by subclasses
        admin(request): Handles admin interface requests, must be implemented by subclasses

    Example:
        class MyPlugin(BasePlugin):
            def __init__(self, app):
                super().__init__(app, 'MyPlugin')
                self.title = "My Custom Plugin"
                self.description = "Example plugin implementation"
                self.category = "Custom"
                self.actions = ['cycle']

            def initialization(self):
                self.logger.info("Plugin initialized")

            def admin(self, request):
                return self.render('admin.html', {'status': 'active'})

            def cyclic_task(self):
                # Background task logic here
                pass
    """

    def __init__(self, app, name):
        self._app = app
        self.name = name
        self.title = "Undefined"
        self.description = "Undefined"
        self.category = "Undefined"
        self.author = "Undefined"
        self.version = 0

        self.system = False
        self.thread = None
        self.dtUpdated = get_now_to_utc()
        self.config = {}

        # Supported Action Types:
        # "cycle": Cyclic background task
        #     - Handler: cyclic_task()
        # "search": Object search functionality
        #     - Handler: search(query: str) -> list[dict]
        #     - Returns formatted results for UI display
        # "widget": Dashboard widget generation
        #     - Handler: widget() -> str
        #     - Returns rendered HTML for control panel
        # "say": Notification/TTS output
        #     - Handler: say(message: str, level: int=0)
        #     - Handles system messages and alerts
        # "proxy": Property change monitoring
        #     - Handler: changeProperty(obj, prop, value)
        #     - Receives all system property changes
        # "playsound": Audio playback
        #     - Handler: playSound(file_name: str, level: int=0)
        #     - Manages sound effects output
        self.actions = []  # list support actions

        self.event = None

        self.logger = getLogger(name)

        self.loadConfig()

        self.blueprint = Blueprint(
            name,
            __name__,
            root_path=Config.PLUGINS_FOLDER,
            template_folder=os.path.join(name, "templates"),
            static_folder=os.path.join(name, "static"),
            static_url_path="/" + name + "/static",
        )
        self.register_routes()
        app.register_blueprint(self.blueprint)

    def register_routes(self):
        for attr_name in dir(self):
            if attr_name.startswith("route_"):
                method = getattr(self, attr_name)
                method()

    def route_admin(self):
        @self.blueprint.route("/admin/" + self.name, methods=["GET", "POST"])
        @handle_admin_required
        def module():
            return self.admin(request)

    def admin(self, request):
        raise NotImplementedError(
            "Subclasses must implement generate_web_content method"
        )

    def render(self, template, content):
        content["segment"] = self.name
        return render_template(template, **content)

    def initialization(self):
        raise NotImplementedError("Subclasses must implement initialization method")

    def is_alive(self):
        if self.thread:
            return self.thread.is_alive()
        return False

    def start_cycle(self):
        """Start cycle"""
        self.logger.info("Starting cycle...")
        if self.thread:
            return
        self.event = Event()
        self.thread = Thread(
            name=f"Thread_{self.name}_cycle", target=self._cyclic_task, daemon=True
        )
        self.thread.start()
        self.logger.info("Started cycle")

    def stop_cycle(self):
        """Stop cycle"""
        self.logger.info("Stopping cycle...")
        self.event.set()
        if self.thread:
            self.thread.join()
            self.thread = None
        self.logger.info("Stopped cycle")

    def _cyclic_task(self):
        while True:
            # check for stop
            if self.event.is_set():
                break

            try:
                self.cyclic_task()
            except Exception as ex:
                self.logger.error(f"Error in cyclic task: {ex}", exc_info=True)

            self.dtUpdated = get_now_to_utc()

    def cyclic_task(self):  
        """  
        Execute cyclic background task for the plugin.  
        
        This method is called repeatedly in a loop by the plugin's background thread  
        when 'cycle' is included in the plugin's actions list. The method runs  
        continuously until the plugin is stopped via stop_cycle().  
        
        The cyclic task execution is managed by _cyclic_task() which:  
        - Calls this method in an infinite loop  
        - Handles exceptions and logs errors  
        - Updates dtUpdated timestamp after each execution  
        - Checks for stop events between iterations  
        
        Override this method in plugin subclasses to implement custom background  
        processing such as:  
        - Periodic data collection from external sources  
        - Regular status checks and monitoring  
        - Scheduled maintenance operations  
        - Continuous sensor reading or device polling  
        
        Note:  
            - This method should not contain infinite loops or blocking operations  
            - Long-running operations should check self.event.is_set() periodically  
            - Exceptions are automatically caught and logged by the framework  
            - The method is called from a daemon thread named 'Thread_{plugin_name}_cycle'  
        
        Example:  
            def cyclic_task(self):  
                # Check sensor every cycle  
                sensor_value = self.read_sensor()  
                if sensor_value > threshold:  
                    self.logger.warning(f"Sensor value high: {sensor_value}")  
                    # Update object property  
                    setProperty("MySensor.value", sensor_value)  
        """  
        pass

    def say(self, message: str, level: int = 0, args=None) -> None:
        """Outputs a message to the system when called in a module with `action="say"`.

        This function processes and displays messages through the system's output channels.
        The module must have `action="say"` configuration to properly handle these calls.

        Args:
            message (str): The text message to be displayed/output
            level (int, optional): Message importance level
            args (dict, optional): Additional parameters for message formatting containing:
                - 'target': Output destination (e.g., 'console', 'log', 'gui')
                - 'format': Message formatting options
                - Any module-specific arguments

        Notes:
            - Message routing depends on system configuration
            - Higher levels may trigger additional system reactions
            - The function typically blocks until output is complete
            - For async operation, use separate threading

        """
        pass

    def changeLinkedProperty(self, obj, prop, val):
        """Modifies a specified property of a linked object and updates any related dependencies.

        This function safely changes the given property (prop) of an object (obj) while ensuring
        that all connected elements (e.g., UI widgets, computed fields, or dependent objects)
        are automatically updated.

        Args:
            obj (object): The target object whose property will be modified.
            prop (str): The name of the property to change.
            val (any): The new value to assign to the property.

        Notes:
            - May include validation checks for the new value.
            - Can trigger additional updates or callback functions.
            - May emit property-change events for observers.
            - Handles cases where the property does not exist or is read-only.

        """
        pass

    def playSound(self, file_name: str, level: int = 0):
        """Plays the specified audio file with optional volume control.

        Designed for modules with `action="playsound"`, this function loads and plays a sound file
        at the given volume level (if supported by the system).

        Args:
            file_name (str): Path to the audio file (e.g., "click.wav").
                Supports common formats (WAV, MP3, etc.; system-dependent).
            level (int, optional): Volume level (0-100, where 0 = default/system volume).
                Values outside this range are clamped. Defaults to 0.

        Raises:
            FileNotFoundError: If `file_name` does not exist.
            RuntimeError: If audio playback fails (e.g., missing codecs or permissions).

        Notes:
            - Non-blocking: Sound plays in the background.
            - Caching: Frequently used files may be cached for performance.
            - Volume: Not all systems support software volume control (level may be ignored).

        """
        pass

    def changeProperty(self, obj: str, prop: str, value) -> None:
        """Receives and processes all property changes from system objects when module has `actions="proxy"`.

        This function serves as a universal property change handler for proxy modules,
        receiving notifications about all property modifications in the system.
        The module must have `actions="proxy"` configuration to activate this functionality.

        Args:
            obj (str): The object whose property was changed
            prop (str): The name of the modified property
            value (Any): The new value of the property

        Notes:
            - This is a read-only observer - modifying properties here may cause infinite loops
            - For performance reasons, frequent property changes may be batched
            - The function should return quickly to avoid system delays
            - Use filters or conditions inside the function to handle only relevant changes

        Typical usage patterns:
            1. Logging/auditing property changes
            2. Synchronizing with external systems
            3. Implementing complex reactive behaviors
            4. Debugging and monitoring object states

        Example:
            >>> def changeProperty(self, obj, prop, value):
            ...     if prop == "temperature" and value > 100:
            ...         self.logWarning(f"High temperature in {obj}: {value}°C")
            ...     # Add custom handling logic here
        """
        pass

    def search(self, query: str) -> list:
        """Searches for linked objects within the module (requires `action="search"` configuration).

        Returns a list of formatted result dictionaries matching the search query, specifically
        designed for integration with web interfaces and object relationship visualization.

        Args:
            query (str): Search string to match against object properties. Supports:
                - Basic text matching
                - Field-specific searches (e.g., "title:router*")
                - Logical operators (AND/OR) when supported

        Returns:
            list: Each item is a dictionary with the following structure:
                {
                    "url": str,    # Direct link to edit/view the object
                    "title": str,  # Display title of the found object
                    "tags": list[dict]  # Contextual tags with colors
                }
            Example:
                [{
                    "url": "Objects?op=edit&device=123",
                    "title": "Relay01",
                    "tags": [{"name": "Objects", "color": "warning"}]
                }]

        Notes:
            - Only active in modules with `action="search"` configuration
            - URL formats are system-dependent
            - Tags support standard color classes (warning, danger, success, etc.)
            - Empty list returned when no matches found

        Typical workflow:
            1. System calls search() when user enters query
            2. Module scans its linked objects
            3. Formats results for UI consumption
            4. Returns structured data for display

        Example:
            >>> results = self.search("main router")
            >>> print(results[0]["title"])  # "Device: Main Router"
        """
        pass

    def widget(self) -> str:
        """Generates a dashboard widget for modules with `actions="widget"` configuration.

        This function is automatically called by the system to render a widget component
        that will be embedded in the main control panel interface.

        Returns:
            str: Rendered HTML content of the widget

        Key Features:
            - Displays essential module information in compact form
            - Provides real-time status overview
            - Supports automatic periodic refreshing
            - Integrates seamlessly with dashboard styling

        Typical Content:
            - Key metrics and statistics
            - Status indicators
            - Activity summaries
            - Quick action links

        Technical Specifications:
            - Uses system's template engine (Jinja2 by default)
            - Data is typically fetched within a database session
            - Output HTML must conform to dashboard styling
            - Must implement responsive design for various panel sizes

        Common Use Cases:
            - Displaying operational statistics
            - Showing system alerts/notifications
            - Presenting status overviews
            - Providing quick access to frequent actions

        Implementation Notes:
            1. Widget template should be stored in module's templates/ directory
            2. Keep content concise - widgets have limited space
            3. Include refresh logic if real-time data is critical
            4. Follow platform's widget styling guidelines

        Security Considerations:
            - All data should be properly sanitized
            - Database queries must use proper scoping
            - HTML output should enable auto-escaping
        """
        pass

    def loadConfig(self):
        """Load plugin configuration"""
        with session_scope() as session:
            rec = session.query(Plugin).filter_by(name=self.name).one_or_none()
            if rec and rec.config:
                self.config = json.loads(rec.config)

                level = self.config.get("level_logging", None)
                if level is None or level == "None":
                    level = "INFO"
                    if Config.DEBUG:
                        level = "DEBUG"
                import logging

                log_level = logging.getLevelName(level)
                self.logger.setLevel(log_level)
                self.logger.info(f"Logger level: {level}")
                self.logger.debug("Config: %s", rec.config)

    def saveConfig(self):
        """Save plugin configuration"""
        with session_scope() as session:
            rec = session.query(Plugin).filter_by(name=self.name).one_or_none()
            if rec:
                rec.config = json.dumps(self.config)
                session.commit()

                level = self.config.get("level_logging", None)
                if level is None or level == "None":
                    level = "INFO"
                    if Config.DEBUG:
                        level = "DEBUG"
                import logging

                log_level = logging.getLevelName(level)
                self.logger.setLevel(log_level)
                self.logger.info(f"Logger level: {level}")

    def sendDataToWebsocket(self, operation: str, data: dict):
        """Send data to websocket"""
        payload = {"operation": operation, "data": data}
        sendDataToWebsocket(self.name, payload)
