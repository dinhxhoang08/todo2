"""Todoist REST API v1 integration (one-way push)."""
import requests

API_BASE = "https://api.todoist.com/api/v1"


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def verify_token(token):
    """Verify Todoist token by fetching projects. Returns True if valid."""
    if not token:
        return False
    try:
        resp = requests.get(
            f"{API_BASE}/projects",
            headers=_headers(token),
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


# Priority mapping: local 0/1/2 → Todoist 1/2/4 (1=normal, 4=urgent)
PRIORITY_MAP = {0: 1, 1: 2, 2: 4}


def create_task(token, title, due_date=None, priority=0, todoist_project_id=None, labels=None):
    """Create a task in Todoist. Returns the task ID or None on failure."""
    if not token:
        return None
    payload = {"content": title, "priority": PRIORITY_MAP.get(priority, 1)}
    if due_date:
        payload["due_date"] = due_date
    if todoist_project_id:
        payload["project_id"] = todoist_project_id
    if labels:
        payload["labels"] = labels
    try:
        resp = requests.post(
            f"{API_BASE}/tasks",
            headers=_headers(token),
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return str(resp.json().get("id", ""))
    except requests.RequestException:
        pass
    return None


def update_task(token, todoist_id, title, due_date=None, priority=0, todoist_project_id=None, labels=None):
    """Update an existing task in Todoist."""
    if not token or not todoist_id:
        return False
    payload = {"content": title, "priority": PRIORITY_MAP.get(priority, 1)}
    if due_date:
        payload["due_date"] = due_date
    else:
        payload["due_string"] = ""  # Clear due date
    if todoist_project_id:
        payload["project_id"] = todoist_project_id
    if labels:
        payload["labels"] = labels
    try:
        resp = requests.post(
            f"{API_BASE}/tasks/{todoist_id}",
            headers=_headers(token),
            json=payload,
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except requests.RequestException:
        return False


def close_task(token, todoist_id):
    """Mark a task as completed in Todoist."""
    if not token or not todoist_id:
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/tasks/{todoist_id}/close",
            headers=_headers(token),
            timeout=10,
        )
        return resp.status_code == 204
    except requests.RequestException:
        return False


def reopen_task(token, todoist_id):
    """Reopen a completed task in Todoist."""
    if not token or not todoist_id:
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/tasks/{todoist_id}/reopen",
            headers=_headers(token),
            timeout=10,
        )
        return resp.status_code == 204
    except requests.RequestException:
        return False


def delete_task(token, todoist_id):
    """Delete a task from Todoist."""
    if not token or not todoist_id:
        return False
    try:
        resp = requests.delete(
            f"{API_BASE}/tasks/{todoist_id}",
            headers=_headers(token),
            timeout=10,
        )
        return resp.status_code == 204
    except requests.RequestException:
        return False



def get_or_create_project(token, name):
    """Find or create a project on Todoist. Returns project_id or None."""
    if not token or not name:
        return None
    try:
        resp = requests.get(f"{API_BASE}/projects", headers=_headers(token), timeout=10)
        if resp.status_code == 200:
            results = resp.json()
            # v1 API wraps in {"results": [...]}
            if isinstance(results, dict) and "results" in results:
                results = results["results"]
            for proj in results:
                if proj.get("name", "").lower() == name.lower():
                    return str(proj["id"])
        # Not found - create it
        resp = requests.post(
            f"{API_BASE}/projects",
            headers=_headers(token),
            json={"name": name},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return str(resp.json().get("id", ""))
    except requests.RequestException:
        pass
    return None

def sync_all_tasks(token, todos):
    """Push all local todos to Todoist. Returns list of (local_id, todoist_id) created."""
    created = []
    if not token:
        return created
    for todo in todos:
        if todo["todoist_id"]:
            # Already synced — update content and ensure completion state
            update_task(token, todo["todoist_id"], todo["title"], todo.get("due_date"), todo.get("priority", 0))
            if todo["completed"]:
                close_task(token, todo["todoist_id"])
            else:
                reopen_task(token, todo["todoist_id"])
        else:
            tid = create_task(token, todo["title"], todo.get("due_date"), todo.get("priority", 0))
            if tid:
                created.append((todo["id"], tid))
                if todo["completed"]:
                    close_task(token, tid)
    return created
