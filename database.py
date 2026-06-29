import sqlite3
from datetime import datetime

DB_NAME = "todos.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            todoist_token TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # Migrate old todos table (no user_id) by dropping it — no user to assign rows to
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(todos)").fetchall()}
    if existing_cols and "user_id" not in existing_cols:
        conn.execute("DROP TABLE todos")
        existing_cols = set()
    if not existing_cols:
        conn.execute(
            """
            CREATE TABLE todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                todoist_id TEXT,
                due_date TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                project_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
            """
        )
    if existing_cols and "due_date" not in existing_cols:
        conn.execute("ALTER TABLE todos ADD COLUMN due_date TEXT")
    if existing_cols and "priority" not in existing_cols:
        conn.execute("ALTER TABLE todos ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
    if existing_cols and "project_id" not in existing_cols:
        conn.execute("ALTER TABLE todos ADD COLUMN project_id INTEGER")
    conn.commit()

    # Create projects table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            todoist_project_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )

    # Create tags table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (user_id, name)
        )
        """
    )

    # Create todo_tags junction table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todo_tags (
            todo_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (todo_id, tag_id),
            FOREIGN KEY (todo_id) REFERENCES todos (id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


# --- User functions ---

def create_user(username, password_hash):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.now().isoformat()),
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, todoist_token FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, todoist_token FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return row


def update_todoist_token(user_id, token):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET todoist_token = ? WHERE id = ?",
        (token if token else None, user_id),
    )
    conn.commit()
    conn.close()


# --- Todo functions ---

def get_all_todos(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, completed, todoist_id, due_date, priority, created_at FROM todos WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def add_todo(user_id, title, due_date=None, priority=0):
    conn = get_connection()
    conn.execute(
        "INSERT INTO todos (user_id, title, completed, due_date, priority, created_at) VALUES (?, ?, 0, ?, ?, ?)",
        (user_id, title, due_date, priority, datetime.now().isoformat()),
    )
    conn.commit()
    todo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return todo_id


def get_todo_by_id(todo_id, user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, title, completed, todoist_id, due_date, priority FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id),
    ).fetchone()
    conn.close()
    return row


def update_todo(todo_id, user_id, title, due_date=None, priority=0):
    conn = get_connection()
    conn.execute(
        "UPDATE todos SET title = ?, due_date = ?, priority = ? WHERE id = ? AND user_id = ?",
        (title, due_date, priority, todo_id, user_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT todoist_id FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id),
    ).fetchone()
    conn.close()
    return row["todoist_id"] if row else None


def toggle_todo(todo_id, user_id):
    conn = get_connection()
    conn.execute(
        "UPDATE todos SET completed = 1 - completed WHERE id = ? AND user_id = ?",
        (todo_id, user_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT completed, todoist_id FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id),
    ).fetchone()
    conn.close()
    return row


def delete_todo(todo_id, user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT todoist_id FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id),
    ).fetchone()
    todoist_id = row["todoist_id"] if row else None
    conn.execute("DELETE FROM todos WHERE id = ? AND user_id = ?", (todo_id, user_id))
    conn.commit()
    conn.close()
    return todoist_id


def delete_all_todos(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT todoist_id FROM todos WHERE user_id = ? AND todoist_id IS NOT NULL",
        (user_id,),
    ).fetchall()
    todoist_ids = [row["todoist_id"] for row in rows]
    conn.execute("DELETE FROM todos WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return todoist_ids


def update_todo_todoist_id(todo_id, todoist_id):
    conn = get_connection()
    conn.execute(
        "UPDATE todos SET todoist_id = ? WHERE id = ?",
        (todoist_id, todo_id),
    )
    conn.commit()
    conn.close()


# --- Project functions ---

def get_projects(user_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.todoist_project_id, p.created_at,
               COUNT(t.id) as todo_count
        FROM projects p
        LEFT JOIN todos t ON t.project_id = p.id AND t.completed = 0
        WHERE p.user_id = ?
        GROUP BY p.id
        ORDER BY CASE WHEN p.name = 'Inbox' THEN 0 ELSE 1 END, p.name ASC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_project(project_id, user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()
    conn.close()
    return row


def ensure_inbox(user_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM projects WHERE user_id = ? AND name = 'Inbox' ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        conn.close()
        return row['id']
    conn.execute(
        "INSERT INTO projects (user_id, name, created_at) VALUES (?, 'Inbox', ?)",
        (user_id, datetime.now().isoformat()),
    )
    inbox_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return inbox_id


def create_project(user_id, name, todoist_project_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (user_id, name, todoist_project_id, created_at) VALUES (?, ?, ?, ?)",
        (user_id, name, todoist_project_id, datetime.now().isoformat()),
    )
    project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return project_id


def update_project_todoist_id(project_id, todoist_project_id):
    conn = get_connection()
    conn.execute(
        "UPDATE projects SET todoist_project_id = ? WHERE id = ?",
        (todoist_project_id, project_id),
    )
    conn.commit()
    conn.close()


def delete_project(project_id, user_id, fallback_project_id):
    conn = get_connection()
    conn.execute(
        "UPDATE todos SET project_id = ? WHERE project_id = ? AND user_id = ?",
        (fallback_project_id, project_id, user_id),
    )
    conn.execute(
        "DELETE FROM projects WHERE id = ? AND user_id = ? AND name != 'Inbox'",
        (project_id, user_id),
    )
    conn.commit()
    conn.close()


# --- Tag functions ---

def get_tags(user_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT tg.id, tg.name, COUNT(tt.todo_id) as todo_count
        FROM tags tg
        LEFT JOIN todo_tags tt ON tt.tag_id = tg.id
        WHERE tg.user_id = ?
        GROUP BY tg.id
        ORDER BY tg.name ASC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_or_create_tag(user_id, name):
    name = name.strip().lower()
    if not name:
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM tags WHERE user_id = ? AND name = ?",
        (user_id, name),
    ).fetchone()
    if row:
        conn.close()
        return row['id']
    conn.execute(
        "INSERT INTO tags (user_id, name, created_at) VALUES (?, ?, ?)",
        (user_id, name, datetime.now().isoformat()),
    )
    tag_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return tag_id


def set_todo_tags(todo_id, tag_ids):
    conn = get_connection()
    conn.execute("DELETE FROM todo_tags WHERE todo_id = ?", (todo_id,))
    for tag_id in tag_ids:
        if tag_id is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO todo_tags (todo_id, tag_id) VALUES (?, ?)",
            (todo_id, tag_id),
        )
    conn.commit()
    conn.close()


def get_todo_tags(todo_id):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT tg.id, tg.name FROM tags tg
        JOIN todo_tags tt ON tt.tag_id = tg.id
        WHERE tt.todo_id = ?
        ORDER BY tg.name ASC
        """,
        (todo_id,),
    ).fetchall()
    conn.close()
    return rows


def delete_tag(tag_id, user_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM tags WHERE id = ? AND user_id = ?",
        (tag_id, user_id),
    )
    conn.commit()
    conn.close()


# --- Extended todo queries ---

def get_todos(user_id, project_id=None, tag_id=None):
    conn = get_connection()
    query = """
        SELECT t.id, t.title, t.completed, t.todoist_id, t.due_date, t.priority,
               t.project_id, t.created_at, p.name as project_name
        FROM todos t
        LEFT JOIN projects p ON p.id = t.project_id
        WHERE t.user_id = ?
    """
    params = [user_id]
    if project_id is not None:
        query += " AND t.project_id = ?"
        params.append(project_id)
    if tag_id is not None:
        query += " AND EXISTS (SELECT 1 FROM todo_tags tt WHERE tt.todo_id = t.id AND tt.tag_id = ?)"
        params.append(tag_id)
    query += " ORDER BY t.created_at DESC, t.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows
