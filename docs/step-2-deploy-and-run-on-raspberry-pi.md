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

- systemd service note
- auto-start on boot