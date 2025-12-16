"""
Flask application for photobooth UI and API.
"""
from pathlib import Path

from flask import Flask, Response, jsonify, request, render_template

from controller.controller import PhotoboothController, Command, CommandType
from controller.gphoto_camera import GPhotoCamera


def create_app(camera=None):
    app = Flask(__name__)

    if camera is None:
        camera = GPhotoCamera()

    controller = PhotoboothController(
        camera=camera,
        image_root=Path("/home/max/photobooth"),
    )
    controller.start()
    app.controller = controller

    @app.route("/api/health")
    def health():
        return app.controller.get_health().to_dict()

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify(app.controller.get_status())

    @app.route("/start-session", methods=["POST"])
    def start_session():
        if app.controller.get_status()["busy"]:
            return jsonify({"ok": False, "error": "busy"}), 409

        data = request.get_json(silent=True) or {}
        print_count = int(data.get("print_count", 1))

        app.controller.enqueue(
            Command(
                CommandType.START_SESSION,
                payload={"print_count": print_count},
            )
        )

        return jsonify({"ok": True})

    @app.route("/take-photo", methods=["POST"])
    def take_photo():
        status = app.controller.get_status()

        if status["state"] != "READY_FOR_PHOTO":
            return jsonify({"ok": False, "error": "not_ready"}), 409

        app.controller.enqueue(
            Command(CommandType.TAKE_PHOTO)
        )

        return jsonify({"ok": True})

    @app.route("/live-view", methods=["GET"])
    def live_view():
        frame = app.controller.get_live_view_frame()
        if not frame:
            return "", 204
        return Response(frame, mimetype="image/jpeg")

    return app
