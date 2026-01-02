"""
WSGI entrypoint for production (gunicorn/systemd).

This module should have no side effects beyond creating the Flask app (which starts the controller).
"""
from web.app import create_app

app = create_app()
