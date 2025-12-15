"""
Flask application for photobooth UI and API.
"""
from pathlib import Path

from flask import Flask, jsonify, request, render_template

from controller.controller import (
    PhotoboothController, Command, CommandType,
)
from tests.fakes.fake_camera import FakeCamera

app = Flask(__name__)

fake_image_dir = Path("/tmp/photobooth_fake_images")
fake_image_dir.mkdir(exist_ok=True)

camera = FakeCamera(fake_image_dir)
controller = PhotoboothController(camera)
controller.start()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/status", methods=["GET"])
def status():
    return jsonify(controller.get_status())


@app.route("/start-session", methods=["POST"])
def start_session():
    if controller.get_status()["busy"]:
        return jsonify({"ok": False, "error": "busy"}), 409

    data = request.get_json(silent=True) or {}
    print_count = int(data.get("print_count", 1))

    controller.enqueue(
        Command(
            CommandType.START_SESSION,
            payload={"print_count": print_count},
        )
    )

    return jsonify({"ok": True})


@app.route("/take-photo", methods=["POST"])
def take_photo():
    status = controller.get_status()

    if status["state"] != "READY_FOR_PHOTO":
        return jsonify({"ok": False, "error": "not_ready"}), 409

    controller.enqueue(
        Command(CommandType.TAKE_PHOTO)
    )

    return jsonify({"ok": True})
