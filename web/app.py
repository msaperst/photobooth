"""
Flask application for photobooth UI and API.
"""
from pathlib import Path

from flask import Flask, Response, jsonify, request, render_template, send_from_directory

from controller.controller import PhotoboothController, Command, CommandType
from controller.gphoto_camera import GPhotoCamera


def create_app(camera=None, image_root: Path | None = None):
    if image_root is None:
        # Default: project root relative to this file
        image_root = Path(__file__).resolve().parents[1]

    app = Flask(__name__)
    app.config["SESSIONS_ROOT"] = image_root / "sessions"

    if camera is None:
        camera = GPhotoCamera()

    controller = PhotoboothController(
        camera=camera,
        image_root=image_root,
    )
    controller.start()
    app.controller = controller

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(controller.get_health().to_dict())

    @app.route("/status", methods=["GET"])
    def status():
        return jsonify(app.controller.get_status())

    @app.route("/live-view", methods=["GET"])
    def live_view():
        frame = app.controller.get_live_view_frame()
        if not frame:
            return "", 204
        return Response(frame, mimetype="image/jpeg")

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

    @app.route("/sessions/<path:filename>")
    def sessions(filename: str):
        sessions_root = app.config["SESSIONS_ROOT"]
        return send_from_directory(str(sessions_root), filename)

    return app
