import os
import json
import time

class LockTimeoutError(Exception):
    pass

def acquire_lock(lock_name: str, timeout: int = 600) -> str:
    """
    Acquires a file-based lock. If the lock exists and is not stale,
    waits until it becomes available or until timeout is reached.
    """
    lock_file = f"{lock_name}.lock" if not lock_name.endswith('.lock') else lock_name
    start_time = time.time()
    pid = os.getpid()

    while time.time() - start_time < timeout:
        if os.path.exists(lock_file):
            try:
                with open(lock_file, "r") as f:
                    lock_data = json.load(f)
                    
                lock_timestamp = lock_data.get("timestamp", 0)
                
                # Check for stale lock (> 10 minutes)
                if time.time() - lock_timestamp > 600:
                    print(f"[{lock_name}] Found stale lock. Removing...")
                    os.remove(lock_file)
                    continue # Try again in the next iteration
            except (json.JSONDecodeError, FileNotFoundError):
                # Lock file is corrupted or just deleted, safe to remove or try again
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                    except:
                        pass
                continue
                
            # Lock is active, wait
            print(f"[{lock_name}] Lock is held by PID {lock_data.get('pid', 'unknown')}. Waiting...")
            time.sleep(10)
        else:
            # Try to acquire lock
            try:
                # Open with 'x' to fail if the file already exists (atomic creation)
                # Wait, 'x' mode is good, but json.dump directly to 'x' is fine
                with open(lock_file, "x") as f:
                    json.dump({"pid": pid, "timestamp": time.time()}, f)
                print(f"[{lock_name}] Acquired lock for PID {pid}.")
                return lock_file
            except FileExistsError:
                # Another process created the file just now
                time.sleep(1)
            except Exception as e:
                print(f"[{lock_name}] Error acquiring lock: {e}")
                time.sleep(1)

    raise LockTimeoutError(f"Failed to acquire lock '{lock_name}' within {timeout} seconds.")

def release_lock(lock_file: str):
    """
    Releases the acquired file-based lock.
    """
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                lock_data = json.load(f)
            
            if lock_data.get("pid") == os.getpid():
                os.remove(lock_file)
                print(f"[{lock_file}] Released lock.")
            else:
                print(f"[{lock_file}] Lock belongs to another PID ({lock_data.get('pid')}). Not removing.")
        except Exception as e:
            print(f"[{lock_file}] Error releasing lock: {e}")
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except:
                    pass
