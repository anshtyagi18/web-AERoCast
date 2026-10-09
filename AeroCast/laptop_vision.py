import os
import sys

# Silence underlying C++ MediaPipe/TFLite warning logs
os.environ["GLOG_minloglevel"] = "2"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import cv2
import math
import time
import json
import ssl
import asyncio
import threading
import urllib.request
from typing import Optional, List, Tuple

# Ensure UTF-8 output encoding for Windows command prompts
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Default WebSocket server URL (WSS over port 8443)
DEFAULT_WS_URL = "wss://127.0.0.1:8443/ws"

class ReceiverState:
    def __init__(self):
        self.status: str = "STANDBY"  # "STANDBY", "FILE_HELD", "COMPLETED"
        self.held_file: Optional[str] = None
        self.drop_triggered: bool = False
        self.flash_counter: int = 0
        self.completed_counter: int = 0
        self.ws_connected: bool = False
        self.send_queue: Optional[asyncio.Queue] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running: bool = True

state = ReceiverState()

async def ws_client_worker(server_url: str):
    """Background WebSocket client with auto-reconnect and self-signed TLS support."""
    state.send_queue = asyncio.Queue()

    # Create unverified SSL context for local self-signed cert
    ssl_context = None
    if server_url.startswith("wss://"):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    while state.running:
        try:
            print(f"[AEROCAST VISION] Connecting to signaling server at {server_url}...")
            async with websockets.connect(server_url, ssl=ssl_context) as ws:
                state.ws_connected = True
                print("[AEROCAST VISION] Connected to AeroCast signaling server.")

                async def receiver_loop():
                    async for message in ws:
                        if not state.running:
                            break
                        try:
                            data = json.loads(message)
                            status = data.get("status")
                            filename = data.get("file") or data.get("filename")

                            if status == "FILE_HELD":
                                state.status = "FILE_HELD"
                                state.held_file = filename
                                state.drop_triggered = False
                                print(f"[AEROCAST VISION] File held in air: '{filename}'")
                            elif status == "COMPLETED":
                                state.status = "COMPLETED"
                                state.held_file = filename
                                state.completed_counter = 75  # ~2.5s banner
                                print(f"[AEROCAST VISION] Transfer complete: '{filename}'")
                            elif status == "STANDBY":
                                state.status = "STANDBY"
                                state.held_file = None
                                state.drop_triggered = False
                        except Exception as e:
                            print(f"[AEROCAST VISION] JSON parse error: {e}")

                async def sender_loop():
                    while state.running:
                        try:
                            payload = await asyncio.wait_for(state.send_queue.get(), timeout=1.0)
                            await ws.send(json.dumps(payload))
                            state.send_queue.task_done()
                        except asyncio.TimeoutError:
                            continue

                await asyncio.gather(receiver_loop(), sender_loop())
        except Exception as e:
            state.ws_connected = False
            if state.running:
                await asyncio.sleep(2)

def start_ws_thread(server_url: str) -> threading.Thread:
    def run():
        loop = asyncio.new_event_loop()
        state.loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ws_client_worker(server_url))
        except Exception:
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t

def emit_air_drop():
    """Queues an AIR_DROP event to send via WebSocket."""
    if state.loop and state.send_queue and not state.loop.is_closed():
        asyncio.run_coroutine_threadsafe(
            state.send_queue.put({"action": "AIR_DROP", "event": "AIR_DROP"}),
            state.loop
        )

# Hand Landmark & Gesture Logic
def distance(p1, p2) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def is_open_palm(landmarks: List[Tuple[float, float]]) -> bool:
    """
    Open Palm Drop Gesture Logic:
    Verifies fingertips (8, 12, 16, 20) are extended away from the wrist (0)
    relative to MCP joints (5, 9, 13, 17) by factor >= 1.25.
    """
    wrist = landmarks[0]
    finger_pairs = [
        (8, 5),    # Index Tip, Index MCP
        (12, 9),   # Middle Tip, Middle MCP
        (16, 13),  # Ring Tip, Ring MCP
        (20, 17)   # Pinky Tip, Pinky MCP
    ]

    for tip_idx, mcp_idx in finger_pairs:
        d_tip = distance(landmarks[tip_idx], wrist)
        d_mcp = distance(landmarks[mcp_idx], wrist)
        if d_mcp == 0:
            return False
        # Fingertip must be extended away from wrist relative to MCP by factor >= 1.25
        if (d_tip / d_mcp) < 1.25:
            return False

    return True

def initialize_hand_detector():
    """
    Initializes MediaPipe hand detection.
    Supports modern MediaPipe Tasks API (Python 3.12+/3.14) and legacy solutions API.
    """
    import mediapipe as mp

    # Check for legacy solutions API
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "hands"):
        print("[AEROCAST VISION] Using MediaPipe Solutions Hands.")
        mp_hands = mp.solutions.hands
        detector = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.75
        )
        def detect_fn(rgb_frame):
            res = detector.process(rgb_frame)
            if res.multi_hand_landmarks:
                pts = [(lm.x, lm.y) for lm in res.multi_hand_landmarks[0].landmark]
                return pts
            return None
        return detect_fn

    # Fallback to modern MediaPipe Tasks API (Tasks Landmarker)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, "hand_landmarker.task")
    if not os.path.exists(model_path):
        print("[AEROCAST VISION] Downloading hand_landmarker.task model...")
        url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        urllib.request.urlretrieve(url, model_path)
        print("[AEROCAST VISION] Model download complete.")

    from mediapipe.tasks.python import vision, BaseOptions
    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.IMAGE,
        num_hands=1,
        min_hand_detection_confidence=0.75,
        min_tracking_confidence=0.75
    )
    landmarker = vision.HandLandmarker.create_from_options(options)
    print("[AEROCAST VISION] Using MediaPipe Tasks HandLandmarker.")

    def detect_tasks_fn(rgb_frame):
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = landmarker.detect(mp_image)
        if result.hand_landmarks and len(result.hand_landmarks) > 0:
            pts = [(lm.x, lm.y) for lm in result.hand_landmarks[0]]
            return pts
        return None

    return detect_tasks_fn

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]

def draw_landmarks(frame, landmarks, is_palm: bool):
    h, w, _ = frame.shape
    color = (0, 235, 120) if is_palm else (180, 180, 180)

    for start, end in HAND_CONNECTIONS:
        pt1 = (int(landmarks[start][0] * w), int(landmarks[start][1] * h))
        pt2 = (int(landmarks[end][0] * w), int(landmarks[end][1] * h))
        cv2.line(frame, pt1, pt2, color, 2, cv2.LINE_AA)

    for i, pt in enumerate(landmarks):
        coord = (int(pt[0] * w), int(pt[1] * h))
        radius = 5 if i in (8, 12, 16, 20, 0) else 3
        cv2.circle(frame, coord, radius, color, -1, cv2.LINE_AA)
        cv2.circle(frame, coord, radius + 1, (255, 255, 255), 1, cv2.LINE_AA)

def run_vision(server_url: str = DEFAULT_WS_URL, stop_event: Optional[threading.Event] = None):
    """
    Main vision loop. Can be called from orchestrator or standalone.
    Runs on the main thread for optimal OpenCV GUI responsiveness on Windows.
    """
    global websockets
    import websockets

    print("=" * 60)
    print("  [AEROCAST] Laptop Vision Receiver Daemon")
    print(f"  Target Signaling Server: {server_url}")
    print("=" * 60)

    start_ws_thread(server_url)
    detect_hands = initialize_hand_detector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam (index 0). Please check your camera permissions.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    palm_streak = 0
    REQUIRED_STREAK = 5  # 5 consecutive validated frames before triggering

    print("\n[READY] AeroCast Receiver daemon active.")
    print("Press 'q' or ESC in the window to exit.\n")

    window_name = "AeroCast Receiver - Laptop Vision"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            if stop_event and stop_event.is_set():
                break

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            # Mirror horizontally
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            landmarks = detect_hands(rgb_frame)
            palm_detected = False

            if landmarks is not None:
                palm_detected = is_open_palm(landmarks)
                draw_landmarks(frame, landmarks, palm_detected)

            # 5-frame streak debounce
            if palm_detected:
                palm_streak += 1
            else:
                palm_streak = 0

            # Trigger condition: 5 consecutive frames of Open Palm while file is held
            if state.status == "FILE_HELD" and not state.drop_triggered:
                if palm_streak >= REQUIRED_STREAK:
                    print(f"[AEROCAST] Open Palm streak reached ({palm_streak} frames)! Triggering AIR_DROP.")
                    state.drop_triggered = True
                    state.flash_counter = 50  # Flash green banner
                    emit_air_drop()

            # Top connection status
            conn_text = "CONNECTED" if state.ws_connected else "CONNECTING..."
            conn_color = (0, 220, 100) if state.ws_connected else (0, 100, 255)
            cv2.putText(frame, f"AEROCAST [{conn_text}]", (24, 38),
                        cv2.FONT_HERSHEY_DUPLEX, 0.65, conn_color, 2, cv2.LINE_AA)

            # UI Overlays
            if state.flash_counter > 0:
                # DROP CONFIRMED! banner
                state.flash_counter -= 1
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, 130), (0, 175, 50), -1)
                cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

                cv2.putText(frame, "DROP CONFIRMED!", (w // 2 - 200, 65),
                            cv2.FONT_HERSHEY_DUPLEX, 1.3, (255, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(frame, "Receiving air teleport payload from phone...", (w // 2 - 240, 105),
                            cv2.FONT_HERSHEY_DUPLEX, 0.7, (240, 255, 240), 1, cv2.LINE_AA)

            elif state.completed_counter > 0:
                state.completed_counter -= 1
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, 130), (20, 140, 40), -1)
                cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

                cv2.putText(frame, "FILE RECEIVED SUCCESSFULLY!", (w // 2 - 280, 65),
                            cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2, cv2.LINE_AA)
                file_disp = state.held_file or "file"
                cv2.putText(frame, f"Saved to static/received/{file_disp}", (w // 2 - 230, 105),
                            cv2.FONT_HERSHEY_DUPLEX, 0.7, (230, 255, 230), 1, cv2.LINE_AA)

            elif state.status == "FILE_HELD":
                # Banner: [AIR TELEPORT: <filename>] - OPEN PALM TO DROP with visual progress meter
                banner_height = 115
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, banner_height), (190, 100, 10), -1) # BGR
                cv2.addWeighted(overlay, 0.88, frame, 0.12, 0, frame)

                file_display = state.held_file if state.held_file else "Selected File"
                if len(file_display) > 26:
                    file_display = file_display[:23] + "..."

                title_text = f"[AIR TELEPORT: {file_display}] - OPEN PALM TO DROP"
                cv2.putText(frame, title_text, (24, 50),
                            cv2.FONT_HERSHEY_DUPLEX, 0.82, (255, 255, 255), 2, cv2.LINE_AA)

                # Visual progress meter
                progress = min(1.0, palm_streak / REQUIRED_STREAK)
                bar_w = 380
                bar_h = 16
                bar_x = 24
                bar_y = 74
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (40, 40, 40), -1)
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + bar_h), (0, 235, 120), -1)
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (255, 255, 255), 1)

                streak_label = f"Palm Streak: {palm_streak}/{REQUIRED_STREAK}"
                cv2.putText(frame, streak_label, (bar_x + bar_w + 14, bar_y + 13),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            else:
                # Standby guidance
                cv2.putText(frame, "AeroCast Receiver - Standby", (24, h - 30),
                            cv2.FONT_HERSHEY_DUPLEX, 0.65, (190, 190, 190), 1, cv2.LINE_AA)
                cv2.putText(frame, "Grab a file into the air on your phone (✊ Fist)", (24, h - 55),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, (140, 140, 140), 1, cv2.LINE_AA)

            if landmarks is not None:
                gesture_text = "OPEN PALM (DROP)" if palm_detected else "HAND DETECTED"
                gesture_col = (0, 235, 120) if palm_detected else (200, 200, 200)
                cv2.putText(frame, gesture_text, (w - 360, h - 30),
                            cv2.FONT_HERSHEY_DUPLEX, 0.65, gesture_col, 2, cv2.LINE_AA)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
    finally:
        state.running = False
        cap.release()
        cv2.destroyAllWindows()
        print("[AEROCAST VISION] Laptop vision receiver daemon closed.")

if __name__ == "__main__":
    run_vision()
