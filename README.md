## Local File Explorer (Flask)

A small Flask app that lets you securely browse and download files from a folder on your machine over HTTP.  
It is designed for **local/LAN use only** (e.g. sharing a folder with phones or other PCs on the same Wi‑Fi) and protects access with a simple token.

### Features

- **Browse any configured folder** from a web UI.
- **View images and videos inline** in the browser.
- **Download files** directly.
- **Token protection** using a shared access token.
- **Safe path resolution** to prevent escaping the configured root.

---

### 1. Requirements

- **Python**: 3.8 or higher
- **Pip**: Python package manager
- (Optional but recommended) **Virtual environment** support: `venv`

---

### 2. Project structure

- `localFileExplorerApp.py` – main Flask application.
- `requirements.txt` – Python dependencies.
- `.gitignore` – ignores common Python build artifacts and virtualenvs.

---

### 3. Installation & setup (any OS)

1. **Clone or download the project**
   ```bash
   git clone https://github.com/<your-username>/<your-repo-name>.git
   cd <your-repo-name>
   ```

2. **Create and activate a virtual environment (recommended)**

   - **Windows (PowerShell)**:
     ```bash
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```

   - **macOS / Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

### 4. Configuration

Open `localFileExplorerApp.py` and adjust the config section near the top:

```python
ROOT_DIR = r"D:\Ring ceremony photos"  # folder you want to share
HOST = "0.0.0.0"                       # "0.0.0.0" makes it reachable on LAN
PORT = 8000
ACCESS_TOKEN = "pandey-9999"           # change to a strong secret
```

- **`ROOT_DIR`**: Set this to the absolute path of the folder you want to expose.
- **`HOST`**:
  - Use `"0.0.0.0"` to allow access from other devices on your LAN.
  - Use `"127.0.0.1"` to restrict access to the same machine.
- **`PORT`**: Any free TCP port, default is `8000`.
- **`ACCESS_TOKEN`**: Change this to a strong, unique token before sharing with others.

> **Important:** This app is intended for trusted networks only. Do **not** expose it directly to the public internet without putting it behind proper authentication and HTTPS.

---

### 5. Running the app

From the project directory (with your virtualenv activated, if using one):

```bash
python localFileExplorerApp.py
```

You should see output like:

```text
Sharing folder: <resolved path>
Open: http://0.0.0.0:8000/?token=<your-token>
```

Open the printed URL in a browser on the same machine.  
If `HOST` is set to `"0.0.0.0"`, replace `0.0.0.0` with your machine’s LAN IP (e.g. `192.168.1.10`) to access it from your phone or other PCs:

```text
http://192.168.1.10:8000/?token=<your-token>
```

You must include the `?token=...` query parameter (or set `X-Token` header) to access the UI.

---

### 6. Running on another system

To run this on a different computer:

1. Install **Python 3.8+** on that machine.
2. Copy or clone the project directory to that machine.
3. Follow the same steps:
   - Create and activate a virtualenv.
   - Run `pip install -r requirements.txt`.
   - Edit `ROOT_DIR` and `ACCESS_TOKEN` in `localFileExplorerApp.py`.
   - Run `python localFileExplorerApp.py`.
4. Visit `http://<machine-ip>:<port>/?token=<your-token>` from a browser on the same network.

---

### 7. Preparing and pushing to GitHub as a new project

From inside the project folder:

1. **Initialize Git (if not already initialized)**
   ```bash
   git init
   ```

2. **Stage files and make the first commit**
   ```bash
   git add .
   git commit -m "Initial commit: local file explorer"
   ```

3. **Create a new empty repository on GitHub**
   - Go to `https://github.com/new`.
   - Set **Repository name** (for example `local-file-explorer`).
   - Leave “Initialize this repository with a README” **unchecked** (you already have one).
   - Click **Create repository**.

4. **Add the GitHub remote and push**
   Replace `<your-username>` and `<your-repo-name>` below:

   ```bash
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

After this, your project is live on GitHub, and future changes can be pushed with:

```bash
git add .
git commit -m "Describe your change"
git push
```

---

### 8. Notes & limitations

- Designed for **personal / LAN use**, not hardened for internet exposure.
- Browser support for certain video formats (e.g. `.mkv`, `.avi`) may vary; users can still download those files.
- Directory traversal is mitigated by safe path resolution within `ROOT_DIR`.

