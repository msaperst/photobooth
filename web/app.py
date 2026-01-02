"""
Flask application for photobooth UI and API.
"""
import os
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_from_directory

from controller.controller import PhotoboothController, Command, CommandType
from controller.gphoto_camera import GPhotoCamera
from controller.health import HealthLevel


def create_app(camera=None, image_root: Path | None = None, *, album_code: str | None = None,
               logo_path: Path | None = None):
    """Create the Flask app.

    Deployment expects configuration via environment variables (loaded by systemd):
      - PHOTOBOOTH_IMAGE_ROOT
      - PHOTOBOOTH_ALBUM_CODE
      - PHOTOBOOTH_LOGO_PATH

    Tests may pass these explicitly.
    """
    # Deployment config is required for operation, but the server should still start
    # (headless Pi) so /healthz can surface actionable errors.
    config_problems: list[str] = []
    env_root = os.getenv("PHOTOBOOTH_IMAGE_ROOT")
    env_album_code = os.getenv("PHOTOBOOTH_ALBUM_CODE")
    env_logo = os.getenv("PHOTOBOOTH_LOGO_PATH")

    if image_root is None:
        if not env_root:
            config_problems.append("PHOTOBOOTH_IMAGE_ROOT is missing")
            image_root = Path("/tmp/photobooth_unconfigured")
        else:
            image_root = Path(env_root)

    if album_code is None:
        if not env_album_code:
            config_problems.append("PHOTOBOOTH_ALBUM_CODE is missing")
            album_code = "MISSING"
        else:
            album_code = env_album_code

    if logo_path is None:
        if not env_logo:
            config_problems.append("PHOTOBOOTH_LOGO_PATH is missing")
            # Safe fallback for startup; operations are gated by health.
            logo_path = Path(__file__).resolve().parents[1] / "imaging" / "logo.png"
        else:
            logo_path = Path(env_logo)

    if logo_path and (not logo_path.exists() or not logo_path.is_file()):
        config_problems.append(f"PHOTOBOOTH_LOGO_PATH is invalid: {logo_path}")

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

    if config_problems:
        controller.set_config_error(
            message="Deployment configuration is missing or invalid",
            instructions=[
                "Fix /etc/photobooth.env and ensure it contains:",
                "  PHOTOBOOTH_IMAGE_ROOT=/var/lib/photobooth",
                "  PHOTOBOOTH_ALBUM_CODE=<EVENT_ALBUM_CODE>",
                "  PHOTOBOOTH_LOGO_PATH=/var/lib/photobooth/logo.png",
                "Problems detected:",
                *[f"  - {p}" for p in config_problems],
                "After fixing config, restart the service:",
                "<code>sudo systemctl restart photobooth</code>",
                "Or power-cycle the Pi.",
            ],
        )
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
        health = controller.get_health()
        if health.level != HealthLevel.OK:
            return jsonify({"ok": False, "error": "unhealthy", "health": health.to_dict()}), 503
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
        health = controller.get_health()
        if health.level != HealthLevel.OK:
            return jsonify({"ok": False, "error": "unhealthy", "health": health.to_dict()}), 503
        app.controller.enqueue(
            Command(CommandType.TAKE_PHOTO)
        )
        return jsonify({"ok": True})

    @app.route("/sessions/<path:filename>")
    def sessions(filename: str):
        sessions_root = app.config["SESSIONS_ROOT"]
        return send_from_directory(str(sessions_root), filename)

    return app
