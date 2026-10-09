import os
import sys
import socket
import datetime
import ipaddress
import asyncio
from typing import Optional, Set, Tuple
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Ensure UTF-8 output encoding for Windows command prompts
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RECEIVED_DIR = os.path.join(STATIC_DIR, "received")
CERTS_DIR = os.path.join(BASE_DIR, "certs")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(RECEIVED_DIR, exist_ok=True)
os.makedirs(CERTS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

DEFAULT_PORT = 8443

def get_lan_ip() -> str:
    """Finds the local network IP via dummy UDP connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def ensure_ssl_certificates(certs_dir: str = CERTS_DIR) -> Tuple[str, str]:
    """
    Checks if SSL certificates exist. If missing, dynamically generates
    a self-signed SSL certificate using cryptography.x509 for LAN IP and localhost.
    """
    os.makedirs(certs_dir, exist_ok=True)
    cert_path = os.path.join(certs_dir, "cert.pem")
    key_path = os.path.join(certs_dir, "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    print("[AEROCAST SSL] Certificates not found. Generating dynamic SSL certs...")
    lan_ip = get_lan_ip()

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AeroCast Air Transfer"),
        x509.NameAttribute(NameOID.COMMON_NAME, lan_ip),
    ])

    # Subject Alternative Names (SAN) for localhost and LAN IP
    san_list = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    try:
        san_list.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
    except ValueError:
        san_list.append(x509.DNSName(lan_ip))

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Save private key
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Save certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[AEROCAST SSL] Successfully generated self-signed certificate for {lan_ip}")
    print(f"               Cert: {cert_path}")
    print(f"               Key:  {key_path}")
    return cert_path, key_path

# State Management for Gestures and Transfers
class TransferStateManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.held_file_name: Optional[str] = None
        self.is_armed: bool = False
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            # Replay current state to newly connected client
            if self.is_armed and self.held_file_name:
                await websocket.send_json({
                    "status": "FILE_HELD",
                    "file": self.held_file_name
                })
            else:
                await websocket.send_json({
                    "status": "STANDBY"
                })

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        async with self._lock:
            disconnected = []
            for connection in list(self.active_connections):
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for dead_ws in disconnected:
                self.active_connections.discard(dead_ws)

    async def arm_grab(self, filename: str):
        async with self._lock:
            self.held_file_name = filename
            self.is_armed = True
        print(f"[AEROCAST SERVER] AIR_GRAB received for file: '{filename}'")
        await self.broadcast({
            "status": "FILE_HELD",
            "file": filename
        })

    async def trigger_drop(self):
        filename = None
        should_drop = False
        async with self._lock:
            if self.is_armed and self.held_file_name:
                filename = self.held_file_name
                should_drop = True
                self.is_armed = False

        if should_drop and filename:
            print(f"[AEROCAST SERVER] AIR_DROP triggered! Executing transfer for '{filename}'")
            await self.broadcast({
                "status": "EXECUTE_TRANSFER",
                "file": filename
            })

    async def cancel(self):
        async with self._lock:
            self.is_armed = False
            self.held_file_name = None
        print("[AEROCAST SERVER] State reset / CANCELLED.")
        await self.broadcast({
            "status": "STANDBY"
        })

    async def mark_completed(self, filename: str):
        async with self._lock:
            self.is_armed = False
            self.held_file_name = None
        print(f"[AEROCAST SERVER] Transfer COMPLETED for '{filename}'")
        await self.broadcast({
            "status": "COMPLETED",
            "file": filename
        })

state_manager = TransferStateManager()

# FastAPI App
app = FastAPI(title="AeroCast Air Transfer Server")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_mobile_client(request: Request):
    lan_ip = get_lan_ip()
    return templates.TemplateResponse(
        request=request,
        name="mobile_client.html",
        context={
            "lan_ip": lan_ip,
            "port": DEFAULT_PORT,
        }
    )

@app.get("/manifest.json")
async def serve_manifest():
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return JSONResponse(status_code=404, content={"error": "Manifest not found"})

@app.get("/sw.js")
async def serve_service_worker():
    sw_path = os.path.join(STATIC_DIR, "js", "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return JSONResponse(status_code=404, content={"error": "Service worker not found"})

@app.post("/transfer")
async def receive_file(file: UploadFile = File(...)):
    """Receives file payload uploaded chunk-by-chunk and broadcasts completion."""
    try:
        # Sanitize filename
        original_name = os.path.basename(file.filename or "transferred_file")
        destination_path = os.path.join(RECEIVED_DIR, original_name)

        # Avoid clobbering existing files by adding timestamp/counter if exists
        base, ext = os.path.splitext(original_name)
        counter = 1
        while os.path.exists(destination_path):
            destination_path = os.path.join(RECEIVED_DIR, f"{base}_{counter}{ext}")
            counter += 1

        print(f"[AEROCAST SERVER] Receiving file '{original_name}' -> saving to '{destination_path}'...")
        chunk_size = 1024 * 64  # 64 KB chunks
        with open(destination_path, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                buffer.write(chunk)

        saved_name = os.path.basename(destination_path)
        file_size_bytes = os.path.getsize(destination_path)
        print(f"[AEROCAST SERVER] File successfully saved: '{saved_name}' ({file_size_bytes} bytes)")

        # Notify all connected peers that the transfer has completed
        await state_manager.mark_completed(saved_name)

        return JSONResponse(content={
            "status": "COMPLETED",
            "file": saved_name,
            "size": file_size_bytes
        })
    except Exception as e:
        print(f"[AEROCAST SERVER ERROR] Transfer failed: {e}")
        return JSONResponse(status_code=500, content={"status": "FAILED", "error": str(e)})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await state_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action") or data.get("event")
            filename = data.get("filename") or data.get("file")

            if action == "AIR_GRAB":
                await state_manager.arm_grab(filename or "file")
            elif action == "AIR_DROP":
                await state_manager.trigger_drop()
            elif action == "CANCEL":
                await state_manager.cancel()
    except WebSocketDisconnect:
        await state_manager.disconnect(websocket)
    except Exception as e:
        print(f"[AEROCAST SERVER] WebSocket error: {e}")
        await state_manager.disconnect(websocket)

def run_server(host: str = "0.0.0.0", port: int = DEFAULT_PORT):
    cert_path, key_path = ensure_ssl_certificates()
    print(f"\n[AEROCAST] Starting HTTPS Server on port {port}...")
    uvicorn.run(
        app,
        host=host,
        port=port,
        ssl_certfile=cert_path,
        ssl_keyfile=key_path,
        log_level="warning"
    )

if __name__ == "__main__":
    run_server()
