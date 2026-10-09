# 🚀 AeroCast: Air Teleport Signaling & Vision System

> **Transfer files between your phone and laptop using intuitive hand gestures — completely web-based, ultra-fast, and 100% local.**

---

## ⚡ What is AeroCast? (In Short & Easy)

**AeroCast** is an "Air Drop" style file transfer system powered by computer vision and local WebSockets.

* **🌐 100% Web-Based Mobile Client:** You **do NOT need to install any app** from Google Play or the App Store on your phone! Simply scan a QR code or visit a local web link in your mobile browser (Safari, Chrome, Firefox, Brave, etc.).
* **✊ Air Grab (Phone):** Pick any file on your phone and hold up a **Fist (✊)** in front of your phone's camera to "grab" the file into thin air.
* **✋ Air Drop (Laptop):** Show an **Open Palm (✋)** to your laptop's webcam to "catch" and drop the file directly onto your computer.
* **🔒 Private & Local:** All transfers occur directly over your local Wi-Fi network (LAN) via high-speed encrypted HTTPS/WSS. No external cloud or third-party servers required.

---

## 🌟 Key Features

| Feature | Description |
| :--- | :--- |
| **Zero App Installation** | Runs instantly inside any mobile browser with Progressive Web App (PWA) support. |
| **Touchless Gestures** | Uses **MediaPipe** AI hand tracking to detect **Fist (Grab)** and **Open Palm (Drop)**. |
| **Instant QR Connection** | Renders an ASCII QR code right in your terminal for immediate 1-second phone pairing. |
| **Real-Time HUD** | Interactive visual HUDs on both the phone browser and laptop OpenCV vision window. |
| **Local HTTPS & WSS** | Automatically generates self-signed SSL/TLS certificates on startup for secure camera access. |
| **One-Click Launch** | Includes automated Windows batch scripts (`run.bat`) for hands-free setup and execution. |

---

## 🔄 How It Works

```text
 📱 Phone (Mobile Browser / PWA)                💻 Laptop / PC (FastAPI + OpenCV)
 ┌───────────────────────────────┐              ┌─────────────────────────────────┐
 │ 1. Pick any file              │              │                                 │
 │ 2. Show Fist (✊) to camera   │              │                                 │
 └──────────────┬────────────────┘              └────────────────┬────────────────┘
                │                                                │
                │  [WSS: AIR_GRAB]                               │  [WSS: AIR_DROP]
                ▼                                                ▼
     ┌──────────────────────────────────────────────────────────────────┐
     │                FastAPI Signaling & Transfer Hub                  │
     │                      (Port 8443 / HTTPS)                         │
     └──────────────────────────────────────────────────────────────────┘
                ▲                                                ▲
                │             [HTTPS Multipart Upload]           │
                └────────────────────────────────────────────────┘
                                        │
                                        ▼
                             📁 Saved to Laptop:
                          `AeroCast/static/received/`
```

---

## 📋 System Requirements

* **Laptop / PC:**
  * Windows 10/11, macOS, or Linux
  * Python **3.10** or higher
  * Built-in webcam or external USB camera
* **Smartphone:**
  * Any modern smartphone (iOS / Android) with a camera
  * Connected to the **same Wi-Fi network** as the laptop

---

## 🚀 Setup & Launch Guide

### Method 1: One-Click Launch (Recommended for Windows)

Simply double-click the **`run.bat`** file in the root folder (or inside the `AeroCast` folder).

The script automatically:
1. Verifies your Python installation.
2. Creates an isolated virtual environment (`venv`).
3. Installs all required dependencies from `requirements.txt`.
4. Generates dynamic SSL certificates if missing.
5. Launches the server and opens the OpenCV receiver camera window.

---

### Method 2: Manual Setup (Step-by-Step)

If you prefer using the command line:

#### 1. Open Terminal & Navigate to `AeroCast`
```bash
cd AeroCast
```

#### 2. Create and Activate Virtual Environment
* **Windows (PowerShell / Command Prompt):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Run AeroCast
```bash
python main.py
```

---

## 📱 Step-by-Step Usage Guide

### Step 1: Connect to the Same Wi-Fi
Ensure your smartphone and your computer are connected to the **same Wi-Fi network**.

### Step 2: Open Mobile Client
When you run `main.py` or `run.bat`, the terminal will display:
* A **QR Code** in ASCII.
* A direct URL such as `https://192.168.1.X:8443`.

Scan the QR code with your phone camera, or manually type the URL into your phone's browser.

> [!NOTE]
> **First-Time SSL Notice on Mobile Browser:**
> Because AeroCast generates a local self-signed certificate for secure camera access, your browser may display a warning:
> * On **Chrome / Android**: Tap **Advanced** &rarr; **Proceed to site (unsafe)**.
> * On **Safari / iOS**: Tap **Show Details** &rarr; **visit this website**.
> * *(This only needs to be approved once).*

### Step 3: Pick a File
On your phone's screen:
1. Tap **"Select File to Cast"**.
2. Choose any photo, video, document, or PDF.

### Step 4: Air Grab (Fist ✊ on Phone)
1. Point your phone's front or back camera at your hand.
2. Form a **Fist (✊)**.
3. Keep the fist held for ~1 second until the streak bar fills up.
4. Your phone will vibrate and signal **"FILE HELD IN AIR"**!

### Step 5: Air Drop (Open Palm ✋ on Laptop)
1. Turn to your laptop screen (the OpenCV camera window).
2. Show an **Open Palm (✋)** to your laptop's camera.
3. The laptop instantly triggers the transfer! The file teleports straight to your computer.

### Step 6: Find Your Received Files
All received files are saved automatically in:
```text
AeroCast/static/received/
```
*(A desktop shortcut `received - Shortcut` is also provided in the root folder).*

---

## 🛠️ Project Structure

```text
Aerocast/
│
├── run.bat                     # Root one-click launcher
├── received - Shortcut.lnk     # Direct shortcut to downloaded files
│
└── AeroCast/
    ├── app.py                  # FastAPI HTTPS server & WebSocket signaling hub
    ├── main.py                 # Unified system orchestrator & terminal QR renderer
    ├── laptop_vision.py        # OpenCV + MediaPipe laptop gesture detector (Palm)
    ├── clean_storage.py        # Utility to clean received files, certs & cache
    ├── requirements.txt        # Python dependency manifest
    ├── run.bat                 # Inner directory launcher script
    │
    ├── templates/
    │   └── mobile_client.html  # Mobile web client (PWA + in-browser MediaPipe)
    │
    ├── static/
    │   ├── css/style.css       # Sleek futuristic dark-mode styling
    │   ├── js/sw.js            # PWA Service Worker for offline capability
    │   ├── icons/              # Web app icons
    │   └── received/           # Destination folder for transferred files
    │
    └── certs/                  # Auto-generated local SSL certificates
```

---

## 🧹 Maintenance & Utilities

To reset the system or clear out transferred test files:

```bash
cd AeroCast
python clean_storage.py
```
This utility provides clean deletion of:
* All files in `static/received/`
* Generated SSL certificates in `certs/` (allows fresh regeneration)
* Python `__pycache__` artifacts

---

## ❓ Troubleshooting & FAQs

### 1. The phone browser says "Site can't be reached" or times out
* Ensure both your phone and laptop are on the **exact same Wi-Fi network**.
* Check your **Windows Firewall** or anti-virus. Ensure Python is allowed through private networks on port `8443`.
* Verify the IP address shown in the terminal matches your machine's current local Wi-Fi IP address.

### 2. Camera preview is black on the phone
* Ensure you accepted the camera permission prompt in your mobile browser.
* Ensure you accepted the self-signed HTTPS certificate (**Advanced** &rarr; **Proceed**). Mobile browsers disable camera access over unverified HTTP.

### 3. Gestures are not triggering
* **Phone Fist (✊):** Keep your fist clearly in front of the camera with good lighting.
* **Laptop Palm (✋):** Face your open hand toward the laptop camera with fingers spread naturally. Ensure your hand is within the camera frame.

### 4. How do I exit?
* Press **`q`** or **`ESC`** while focused on the laptop camera preview window, or press **`Ctrl + C`** in the terminal.

---

## 📜 Tech Stack

* **Backend & Networking:** [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), WebSockets, Python Cryptography (`x509`)
* **Computer Vision & AI:** [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker), [OpenCV](https://opencv.org/)
* **Mobile Frontend:** HTML5, CSS3, JavaScript, MediaPipe Hands JS, PWA (Service Workers)
"# web-AERoCast" 
