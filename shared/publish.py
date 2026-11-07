"""
publish.py - save this repo's state and put docs/ live on the public website.

  commit_and_push(message, paths)  commit the given files/folders here and push
  deploy_site(message)             make the website repo (WEBSITE_REPO) an exact copy of docs/
"""
import os
import shutil
import stat
import subprocess

WEBSITE_REPO = os.getenv("WEBSITE_REPO", "harshhaldankar/Getyourdeal")
DEPLOY_DIR = "_website_deploy"


def _git(*args, cwd=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, check=check, capture_output=True, text=True)


def _set_identity(cwd=None):
    _git("config", "user.name", "github-actions[bot]", cwd=cwd, check=False)
    _git("config", "user.email", "github-actions[bot]@users.noreply.github.com", cwd=cwd, check=False)


def commit_and_push(message: str, paths: list) -> bool:
    """Commit `paths` (deletions included) and push, rebasing over anything pushed meanwhile."""
    try:
        _set_identity()
        _git("add", "-A", "--", *paths)
        if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
            print("[PUBLISH] Nothing to commit.")
            return True
        _git("commit", "-m", message)
        for _ in range(3):
            if _git("pull", "--rebase", "--autostash", "origin", "master", check=False).returncode == 0:
                if _git("push", check=False).returncode == 0:
                    print("[PUBLISH] Pushed.")
                    return True
            else:
                _git("rebase", "--abort", check=False)
        print("[PUBLISH] Push failed after 3 tries.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[PUBLISH] Git failed: {e.stderr or e}")
        return False


def _remove(path):
    def unlock(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=unlock)
    elif os.path.exists(path):
        os.remove(path)


def _ensure_pages_built(token: str, minutes: int = 14):
    """GitHub Pages sometimes times out publishing a push ("Page build failed"); start it once more."""
    import time
    import requests
    api = f"https://api.github.com/repos/{WEBSITE_REPO}/pages/builds"
    head = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    retried = False
    end = time.time() + minutes * 60
    time.sleep(20)
    while time.time() < end:
        try:
            status = requests.get(f"{api}/latest", headers=head, timeout=30).json().get("status")
        except Exception:
            status = None
        if status == "built":
            print("[DEPLOY] Website is live.")
            return True
        if status == "errored" and not retried:
            print("[DEPLOY] GitHub Pages failed to publish; trying again.")
            requests.post(api, headers=head, timeout=30)
            retried = True
        time.sleep(30)
    print("[DEPLOY] GitHub Pages hasn't finished; it may still go live in a few minutes.")
    return False


def deploy_site(message: str) -> bool:
    """Mirror docs/ into the website repo: new and changed files go up, removed ones are deleted."""
    token = os.getenv("WEBSITE_DEPLOY_TOKEN")
    if not token:
        print("[DEPLOY] WEBSITE_DEPLOY_TOKEN not set; skipping website deploy.")
        return False
    try:
        _remove(DEPLOY_DIR)
        _git("clone", "--depth", "1", f"https://x-access-token:{token}@github.com/{WEBSITE_REPO}.git", DEPLOY_DIR)
        for item in os.listdir(DEPLOY_DIR):
            if item not in (".git", "CNAME"):
                _remove(os.path.join(DEPLOY_DIR, item))
        for item in os.listdir("docs"):
            src, dst = os.path.join("docs", item), os.path.join(DEPLOY_DIR, item)
            (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
        _set_identity(DEPLOY_DIR)
        _git("add", "-A", cwd=DEPLOY_DIR)
        if _git("diff", "--cached", "--quiet", cwd=DEPLOY_DIR, check=False).returncode == 0:
            print("[DEPLOY] Website already up to date.")
        else:
            _git("commit", "-m", message, cwd=DEPLOY_DIR)
            _git("push", cwd=DEPLOY_DIR)
            print("[DEPLOY] Website updated.")
            _ensure_pages_built(token)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[DEPLOY] Failed: {e.stderr or e}")
        return False
    finally:
        try:
            _remove(DEPLOY_DIR)
        except OSError:
            pass  # Windows can hold git's pack files a moment longer; the next deploy clears it
