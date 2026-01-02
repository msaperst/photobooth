"""
Flask application for photobooth UI and API.
"""
import os
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory

from controller.controller import PhotoboothController, Command, CommandType
from controller.gphoto_camera import GPhotoCamera


def create_app(camera=None, image_root: Path | None = None, *, album_code: str | None = None,
               logo_path: Path | None = None):
    """Create the Flask app.

    Deployment expects configuration via environment variables (loaded by systemd):
      - PHOTOBOOTH_IMAGE_ROOT
      - PHOTOBOOTH_ALBUM_CODE
      - PHOTOBOOTH_LOGO_PATH

    Tests may pass these explicitly.
    """
    if image_root is None:
        env_root = os.getenv("PHOTOBOOTH_IMAGE_ROOT")
        if not env_root:
            raise RuntimeError("PHOTOBOOTH_IMAGE_ROOT is required (e.g. /var/lib/photobooth)")
        image_root = Path(env_root)

    if album_code is None:
        album_code = os.getenv("PHOTOBOOTH_ALBUM_CODE")
        if not album_code:
            raise RuntimeError("PHOTOBOOTH_ALBUM_CODE is required (event album code)")

    if logo_path is None:
        env_logo = os.getenv("PHOTOBOOTH_LOGO_PATH")
        if not env_logo:
            raise RuntimeError("PHOTOBOOTH_LOGO_PATH is required (path to logo.png)")
        logo_path = Path(env_logo)

    if not logo_path.exists() or not logo_path.is_file():
        raise RuntimeError(f"PHOTOBOOTH_LOGO_PATH does not exist or is not a file: {logo_path}")

    app = Flask(__name__)
    sessions_root = image_root / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)
    app.config["SESSIONS_ROOT"] = sessions_root

    if camera is None:
        camera = GPhotoCamera()

    controller = PhotoboothController(
        camera=camera,
        image_root=image_root,
        strip_logo_path=logo_path,
        event_album_code=album_code,
    )
    controller.start()
    app.controller = controller

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(controller.get_health().to_dict())

    # an alias of the above health - might be modified in the future
    # to contain system information
    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify(controller.get_health().to_dict())

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
        app.controller.enqueue(
            Command(CommandType.TAKE_PHOTO)
        )
        return jsonify({"ok": True})

    @app.route("/sessions/<path:filename>")
    def sessions(filename: str):
        sessions_root = app.config["SESSIONS_ROOT"]
        return send_from_directory(str(sessions_root), filename)

    return app
