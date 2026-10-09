import os
import sys

# Silence underlying C++ MediaPipe/TFLite warning logs
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import time
import socket
import threading
import qrcode
import uvicorn

# Configure Windows terminal for UTF-8 support
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import app
import laptop_vision

def check_virtual_environment():
    """Checks if running inside a virtual environment and prints status."""
    is_venv = (
        hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix)
        or "VIRTUAL_ENV" in os.environ
    )
    if is_venv:
        print(" [ENV] Virtual environment active.")
    else:
        print("⚠️ [ENV] Warning: Not running inside a virtual environment.")

def display_qr_code(url: str):
    """Renders QR code directly in the terminal for fast phone scanning."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2
        )
        qr.add_data(url)
        qr.make(fit=True)
        print("\n  Scan with your phone camera:")
        try:
            qr.print_ascii(invert=True)
        except Exception:
            qr.print_tty()
    except Exception as e:
        print(f"  (Terminal QR render skipped: {e})")

def main():
    print("\n" + "=" * 64)
    print("      🚀 AEROCAST: AIR TELEPORT SIGNALING & VISION SYSTEM")
    print("=" * 64)

    # 1. Environment check
    check_virtual_environment()

    # 2. SSL Certificate Generation
    cert_path, key_path = app.ensure_ssl_certificates()

    # 3. Discovery & Networking
    lan_ip = app.get_lan_ip()
    port = app.DEFAULT_PORT
    server_https_url = f"https://{lan_ip}:{port}"
    server_wss_local = f"wss://127.0.0.1:{port}/ws"

    print("-" * 64)
    print(f"  🌐 MOBILE CLIENT URL : {server_https_url}")
    print(f"  🔌 LOCAL WSS TARGET   : {server_wss_local}")
    print(f"  🔒 SSL CERTIFICATE    : {cert_path}")
    print("-" * 64)
    print("  📱 Connect your phone to the SAME Wi-Fi network.")
    print("  ⚠️  ON MOBILE BROWSER (First Time SSL Trust):")
    print("      Tap 'Advanced' -> 'Proceed to this site (unsafe)'")
    print("      (Required once for self-signed camera access on LAN)")
    print("-" * 64)

    # 4. Display QR Code
    display_qr_code(server_https_url)

    print("\n" + "=" * 64)
    print("  Starting unified background HTTPS server & main vision thread...")
    print("  Press 'q' or ESC in the camera window to exit.")
    print("=" * 64 + "\n")

    # 5. Launch Uvicorn in background thread
    server_config = uvicorn.Config(
        app.app,
        host="0.0.0.0",
        port=port,
        ssl_certfile=cert_path,
        ssl_keyfile=key_path,
        log_level="warning"
    )
    server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Give server a brief moment to bind port
    time.sleep(1.0)

    stop_event = threading.Event()

    try:
        # 6. Run OpenCV laptop vision receiver on the main thread for optimal Windows rendering
        laptop_vision.run_vision(server_url=server_wss_local, stop_event=stop_event)
    except KeyboardInterrupt:
        print("\n[AEROCAST] Shutdown initiated by KeyboardInterrupt.")
    finally:
        print("[AEROCAST] Cleaning up services...")
        stop_event.set()
        server.should_exit = True
        # Allow background threads to finish
        server_thread.join(timeout=2.0)
        print("[AEROCAST] System shut down cleanly. Goodbye!")

if __name__ == "__main__":
    main()
