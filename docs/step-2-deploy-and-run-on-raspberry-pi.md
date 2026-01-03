> **Automation available**
>
> All steps in this document can be performed automatically using:
> `deployment/scripts/step2_deploy_app.sh`
>
> The script installs the application, configures systemd, and starts the service.

# Step 2: Deploy and Run on Raspberry Pi

This step assumes Raspberry Pi OS is installed and basic dependencies are in place (see Step 0 and Step 1).

Goals:

- Deploy the repo to a known location on the Pi
- Create a dedicated Python virtual environment
- Configure event-level settings outside the repo
- Run the app as a systemd service (auto-start + auto-restart)
- Provide simple operator commands for health checks and logs

---

## 2.1 Choose install and data locations

Recommended locations:

- Code (git checkout): /opt/photobooth
- Python venv: /opt/photobooth/venv
- Data root (sessions/images): /var/lib/photobooth
- Event logo: /var/lib/photobooth/logo.png
- Environment file: /etc/photobooth.env
- systemd unit: /etc/systemd/system/photobooth.service

Notes:

- The app does NOT store sessions inside the repo checkout.
- All session files live under PHOTOBOOTH_IMAGE_ROOT/sessions.

---

## 2.2 Deploy code from GitHub

If /opt does not exist or is restricted, use /srv instead. These docs assume /opt/photobooth.

```bash
sudo mkdir -p /opt/photobooth
sudo chown -R photobooth:photobooth /opt/photobooth
```

As the photobooth user:

```bash
sudo -u photobooth -H bash
cd /opt/photobooth

# Clone once
git clone <YOUR_GITHUB_REPO_URL> .

# Checkout the branch/tag you want to run
git checkout main
git pull
```

> _**An auto-update script lives at deployment/update_repo.sh
> and is invoked by systemd.**_
> - This script is designed to be safe at boot:
    >
- If Ethernet is not available, it exits without blocking startup.
>   - If dependencies cannot be updated (requirements changed and pip install fails), it keeps the old code checked out.
> - This feature requires the systemd unit to include: `ExecStartPre=-/opt/photobooth/deployment/update_repo.sh`

---

## 2.3 Create virtual environment and install dependencies

As the photobooth user:

```bash
cd /opt/photobooth
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
./venv/bin/python -m pip install -r requirements.txt
```

---

## 2.4 Create the data root and place the event logo

```bash
sudo mkdir -p /var/lib/photobooth/sessions
sudo chown -R photobooth:photobooth /var/lib/photobooth
sudo chmod 777 /var/lib/photobooth  #optional
```

Copy your event logo to the Pi:

```bash
# From your laptop (example)
scp ./logo.png photobooth@<PI_HOSTNAME_OR_IP>:/var/lib/photobooth/logo.png
```

---

## 2.5 Configure event settings (/etc/photobooth.env)

Copy the example env file:

```bash
sudo cp /opt/photobooth/deployment/photobooth.env.example /etc/photobooth.env
sudo chown root:root /etc/photobooth.env
sudo chmod 0644 /etc/photobooth.env
```

Edit it:

```bash
sudo vim /etc/photobooth.env
```

Required values:

- PHOTOBOOTH_IMAGE_ROOT=/var/lib/photobooth
- PHOTOBOOTH_LOGO_PATH=/var/lib/photobooth/logo.png
- PHOTOBOOTH_ALBUM_CODE=CHANGE_ME

Important:

- The service will start even if these values are missing (headless Pi), but the booth will be UNHEALTHY.
- When unhealthy, /healthz will show an explicit CONFIG_INVALID error with exact fix instructions.
- The UI/API will refuse to start sessions or take photos while unhealthy.

After changing /etc/photobooth.env or replacing the logo, restart the service:

```bash
sudo systemctl restart photobooth
```

Or power-cycle the Pi.

---

## 2.6 Install and enable the systemd service

Install the unit file:

```bash
sudo cp /opt/photobooth/deployment/systemd/photobooth.service /etc/systemd/system/photobooth.service
sudo systemctl daemon-reload
sudo systemctl enable photobooth
sudo systemctl start photobooth
```

> The systemd unit uses
> `/opt/photobooth/venv/bin/python -m gunicorn`
> to avoid issues with missing gunicorn executables.

Check status:

```bash
systemctl status photobooth --no-pager
```

---

## 2.7 Verify health and view logs

Health:

```bash
curl http://localhost:5000/healthz
```

Logs:

```bash
journalctl -u photobooth -f
```

---

## 2.8 Manual run (for debugging)

This runs the same way as systemd, but in your terminal:

```bash
cd /opt/photobooth
./venv/bin/gunicorn --workers 1 --threads 1 --bind 0.0.0.0:5000 web.wsgi:app
```

If the service is running, stop it first:

```bash
sudo systemctl stop photobooth
```
