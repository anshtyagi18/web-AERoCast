import os
import shutil
import sys

# Configure UTF-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
RECEIVED_DIR = os.path.join(STATIC_DIR, "received")
CERTS_DIR = os.path.join(BASE_DIR, "certs")

def clean_received_files():
    """Removes all transferred files in static/received."""
    if not os.path.exists(RECEIVED_DIR):
        os.makedirs(RECEIVED_DIR, exist_ok=True)
        print("📁 static/received directory created.")
        return 0

    count = 0
    for filename in os.listdir(RECEIVED_DIR):
        file_path = os.path.join(RECEIVED_DIR, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
                count += 1
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                count += 1
        except Exception as e:
            print(f"⚠️ Could not delete {file_path}: {e}")
    print(f"🗑️  Cleared {count} file(s) from static/received/")
    return count

def clean_certs():
    """Removes generated SSL certificates to allow fresh regeneration."""
    count = 0
    if os.path.exists(CERTS_DIR):
        for item in os.listdir(CERTS_DIR):
            item_path = os.path.join(CERTS_DIR, item)
            try:
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    count += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    count += 1
            except Exception as e:
                print(f"⚠️ Could not delete cert {item_path}: {e}")
        print(f"🔒 Cleared {count} certificate file(s) from certs/")
    else:
        print("🔒 No certs directory found.")
    return count

def clean_pycache():
    """Removes all __pycache__ folders and .pyc files recursively."""
    count = 0
    for root, dirs, files in os.walk(BASE_DIR):
        if "__pycache__" in dirs:
            pycache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(pycache_dir)
                count += 1
            except Exception as e:
                print(f"⚠️ Could not delete {pycache_dir}: {e}")
        for f in files:
            if f.endswith(".pyc") or f.endswith(".pyo"):
                try:
                    os.remove(os.path.join(root, f))
                    count += 1
                except Exception:
                    pass
    print(f"🧹 Removed {count} python cache artifact(s).")
    return count

def main():
    print("=" * 60)
    print("  [AEROCAST] Clean Storage & Reset Utility")
    print("=" * 60)
    clean_received_files()
    clean_certs()
    clean_pycache()
    print("-" * 60)
    print("✨ Reset complete! You can now run AeroCast with a fresh state.")

if __name__ == "__main__":
    main()
