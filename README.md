# A server wrapper for OrcaSlicer

## SETUP

### Linux (Debian/Ubuntu)

Run once from this folder, as your normal user (it asks for sudo where needed):

```bash
bash setup.sh "http://localhost:5173,https://domain.com"
```

The argument is the comma-separated list of sites allowed to call the server (CORS), no spaces.
The script downloads OrcaSlicer 2.5.1 to `~/orcaslicer-2.5.1`, makes the venv, test-slices `models/cube.stl`
and installs the `orca-slicer` systemd service on port 8000. Running it again is safe.

After pulling new code: `sudo systemctl restart orca-slicer`

By hand instead:

1. python3 -m venv .venv

2. .venv/bin/pip install -r requirements.txt

3. export ORCA_PATH=~/orcaslicer-2.5.1/AppRun   (the unpacked OrcaSlicer AppImage)

4. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
