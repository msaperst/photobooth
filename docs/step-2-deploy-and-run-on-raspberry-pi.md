# TODO

- checkout code from git
- have code on startup

do an http clone
do a pull on branch you want to deploy
launch flask

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
flask --app web.app run --host=0.0.0.0 --port=5000
```