import os

from datetime import date

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
import todoist

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

db.init_db()


# --- User model for flask-login ---

class User(UserMixin):
    def __init__(self, id, username, todoist_token=None):
        self.id = id
        self.username = username
        self.todoist_token = todoist_token


@login_manager.user_loader
def load_user(user_id):
    row = db.get_user_by_id(int(user_id))
    if row:
        return User(row["id"], row["username"], row["todoist_token"])
    return None


# --- Auth routes ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Vui lòng nhập đầy đủ username và password.", "error")
            return render_template("register.html")
        if len(password) < 4:
            flash("Password phải có ít nhất 4 ký tự.", "error")
            return render_template("register.html")
        pw_hash = generate_password_hash(password)
        user_id = db.create_user(username, pw_hash)
        if user_id is None:
            flash("Username đã tồn tại.", "error")
            return render_template("register.html")
        user = User(user_id, username)
        login_user(user)
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = db.get_user_by_username(username)
        if row and check_password_hash(row["password_hash"], password):
            user = User(row["id"], row["username"], row["todoist_token"])
            login_user(user)
            return redirect(url_for("index"))
        flash("Sai username hoặc password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# --- Settings ---

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        token = request.form.get("todoist_token", "").strip()
        if token and not todoist.verify_token(token):
            flash("Token không hợp lệ — không thể kết nối Todoist. Vui lòng kiểm tra lại.", "error")
            return render_template("settings.html")
        db.update_todoist_token(current_user.id, token)
        current_user.todoist_token = token or None
        flash("Đã lưu Todoist API token." if token else "Đã xoá Todoist API token.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html")


# --- Todo routes ---

@app.route("/")
@login_required
def index():
    todos = db.get_all_todos(current_user.id)
    return render_template("index.html", todos=todos, today=date.today().isoformat())


@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    priority = int(request.form.get("priority", 0))
    if title:
        todo_id = db.add_todo(current_user.id, title, due_date, priority)
        tid = todoist.create_task(current_user.todoist_token, title, due_date, priority)
        if tid:
            db.update_todo_todoist_id(todo_id, tid)
    return redirect(url_for("index"))


@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    todo = db.get_todo_by_id(todo_id, current_user.id)
    if not todo:
        return redirect(url_for("index"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        priority = int(request.form.get("priority", 0))
        if title:
            todoist_id = db.update_todo(todo_id, current_user.id, title, due_date, priority)
            todoist.update_task(current_user.todoist_token, todoist_id, title, due_date, priority)
        return redirect(url_for("index"))
    return render_template("edit.html", todo=todo)


@app.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    row = db.toggle_todo(todo_id, current_user.id)
    if row and row["todoist_id"]:
        if row["completed"]:
            todoist.close_task(current_user.todoist_token, row["todoist_id"])
        else:
            todoist.reopen_task(current_user.todoist_token, row["todoist_id"])
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    todoist_id = db.delete_todo(todo_id, current_user.id)
    todoist.delete_task(current_user.todoist_token, todoist_id)
    return redirect(url_for("index"))


@app.route("/delete_all", methods=["POST"])
@login_required
def delete_all():
    todoist_ids = db.delete_all_todos(current_user.id)
    for tid in todoist_ids:
        todoist.delete_task(current_user.todoist_token, tid)
    return redirect(url_for("index"))


@app.route("/sync", methods=["POST"])
@login_required
def sync():
    if not current_user.todoist_token:
        flash("Chưa cấu hình Todoist API token. Vào Settings để thêm.", "error")
        return redirect(url_for("index"))
    if not todoist.verify_token(current_user.todoist_token):
        flash("Todoist API token không hợp lệ hoặc hết hạn. Kiểm tra lại trong Settings.", "error")
        return redirect(url_for("index"))
    todos = db.get_all_todos(current_user.id)
    created = todoist.sync_all_tasks(current_user.todoist_token, todos)
    for local_id, tid in created:
        db.update_todo_todoist_id(local_id, tid)
    already_synced = sum(1 for t in todos if t["todoist_id"])
    new_synced = len(created)
    total = already_synced + new_synced
    if new_synced == 0 and already_synced == 0 and len(todos) > 0:
        flash("Không thể đồng bộ. Kiểm tra lại Todoist API token.", "error")
    else:
        flash(f"Đã đồng bộ {total}/{len(todos)} todo lên Todoist ({new_synced} mới tạo).", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8011, debug=False)
