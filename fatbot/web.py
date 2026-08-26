import logging
import threading

from flask import Flask

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return "Hello World"

    @app.get("/health")
    def health():
        return "ok"

    return app


def start_web(port: int):
    app = create_app()
    thread = threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    thread.start()
