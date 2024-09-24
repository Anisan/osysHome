""" Base class plugin """
import os
import json
import datetime
from threading import Thread, Event
from flask import Blueprint, request, render_template
from settings import Config
from app.core.models.Plugins import Plugin
from app.database import session_scope
from app.authentication.handlers import handle_admin_required
from app.logging_config import getLogger

class BasePlugin:
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
        self.dtUpdated = datetime.datetime.now()
        self.config = {}
        self.actions = []  # list support actions

        self.event = None

        self.loadConfig()

        level = self.config.get("level_logging", None)
        self.logger = getLogger(name, level)

        self.blueprint = Blueprint(name,
                                   __name__,
                                   root_path=Config.PLUGINS_FOLDER,
                                   template_folder=os.path.join(name, 'templates'),
                                   static_folder=os.path.join(name, 'static'),
                                   static_url_path='/' + name + '/static'
                                   )
        self.register_routes()
        app.register_blueprint(self.blueprint)

    def register_routes(self):
        for attr_name in dir(self):
            if attr_name.startswith('route_'):
                method = getattr(self, attr_name)
                method()

    def route_admin(self):
        @self.blueprint.route("/admin/" + self.name, methods=['GET','POST'])
        @handle_admin_required
        def funcAdmin():
            return self.admin(request)

    def admin(self, request):
        raise NotImplementedError("Subclasses must implement generate_web_content method")

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
        """ Start cycle """
        self.logger.info("Starting cycle...")
        if self.thread:
            return
        self.event = Event()
        self.thread = Thread(name=f'Thread_{self.name}_cycle', target=self._cyclic_task, daemon=True)
        self.thread.start()
        self.logger.info("Started cycle")

    def stop_cycle(self):
        """ Stop cycle """
        self.logger.info("Stoping cycle...")
        self.event.set()
        if self.thread:
            self.thread.join()
            self.thread = None
        self.logger.info("Stoped cycle")

    def _cyclic_task(self):
        while True:
            # check for stop
            if self.event.is_set():
                break
            
            try:
                self.cyclic_task()
            except Exception as ex:
                self.logger.error(f"Error in cyclic task: {ex}")

            self.dtUpdated = datetime.datetime.now()

    def cyclic_task(self):
        pass

    def changeLinkedProperty(self, obj, prop, val):
        pass

    def loadConfig(self):
        """ Load plugin configuration """
        with session_scope() as session:
            rec = session.query(Plugin).filter_by(name=self.name).one_or_none()
            if rec:
                if rec.config:
                    self.config = json.loads(rec.config)

    def saveConfig(self):
        """ Save plugin configuration """
        with session_scope() as session:
            rec = session.query(Plugin).filter_by(name=self.name).one_or_none()
            if rec:
                rec.config = json.dumps(self.config)
                session.commit()
