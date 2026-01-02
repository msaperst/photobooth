# TODO

- checkout code from git
- have code on startup

do an http clone
do a pull on branch you want to deploy
launch flask

## 2.1 Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2.2 Install Dependencies

```bash
python -m pip install -r requirements.txt
```

## 2.3 Run Application

```bash
flask --app web.app run --host=0.0.0.0 --port=5000
```

## Notes

Verify the server is running:

- Health (controller health summary): GET /health or GET /healthz
- Status (UI/session state): GET /status
  Example:

```bash
curl http://localhost:5000/healthz

curl http://localhost:5000/status
```

Still Need:

- systemd service note
- auto-start on boot
  (We’ll expand this doc heavily once we implement systemd + `/etc/photobooth.env`.)

---