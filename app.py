from flask import Flask, request, redirect, url_for, render_template_string, session
import os
import sqlite3
import psycopg2
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mayday-secret-key-change-me")

# 固定两个槽位：用户一 / 用户二
SLOTS = ["user1", "user2"]

LOGIN_PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>登录 - 五月天点歌</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 560px; margin: 60px auto; padding: 0 16px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 18px; }
    input, select { padding: 10px; width: 100%; box-sizing: border-box; margin: 10px 0; }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid #333; background: #111; color: #fff; cursor: pointer; }
    .muted { color: #666; font-size: 14px; }
    .err { color: #b00020; margin-top: 8px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>先选你是“用户一/用户二”，再输入昵称</h2>
    <div class="muted">昵称支持中英文、符号；用于页面显示。</div>
    <form method="post" action="/login">
      <label>你是谁？</label>
      <select name="slot" required>
        <option value="user1">用户一</option>
        <option value="user2">用户二</option>
      </select>
      <label>你的昵称</label>
      <input name="name" placeholder="比如：小蝴蝶🦋 / 五月天研究员 / TT" required>
      <button type="submit">进入</button>
    </form>
    {% if error %}
      <div class="err">{{ error }}</div>
    {% endif %}
  </div>
</body>
</html>
"""

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>五月天每周点歌</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 980px; margin: 30px auto; padding: 0 16px; }
    h1 { margin-bottom: 6px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 14px 16px; margin: 14px 0; }
    input { padding: 8px; margin: 6px 0; width: 100%; box-sizing: border-box; }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid #333; background: #111; color: #fff; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px; border-bottom: 1px solid #eee; }
    .muted { color: #666; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    @media (max-width: 760px) { .row { grid-template-columns: 1fr; } }
    .pill { display: inline-block; padding: 3px 10px; border: 1px solid #ddd; border-radius: 999px; font-size: 13px; margin-left: 8px; }
    .topline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .linkbtn { margin-left: auto; font-size: 14px; }
    .linkbtn a { color: #111; text-decoration: none; border-bottom: 1px dashed #111; }
    ol { margin: 8px 0 0 18px; }
  </style>
</head>
<body>
  <div class="topline">
    <h1>五月天每周点歌</h1>
    <span class="pill">当前周：{{ week_id }}</span>
    <span class="pill">你：<b>{{ me_name }}</b>（{{ me_label }}）</span>
    <span class="pill">对方：<b>{{ other_name }}</b>（{{ other_label }}）</span>
    <div class="linkbtn"><a href="/logout">切换用户</a></div>
  </div>

  <div class="card">
    <h2>提交本周 3 首歌</h2>
    <div class="muted">同一周同一用户：最多保留最新一次提交（可覆盖本周选择）。</div>
    <form method="post" action="/submit">
      <label>第 1 首</label>
      <input name="song1" placeholder="比如：突然好想你" required>

      <label>第 2 首</label>
      <input name="song2" placeholder="比如：倔强" required>

      <label>第 3 首</label>
      <input name="song3" placeholder="比如：温柔" required>

      <button type="submit">提交</button>
    </form>
  </div>

  <div class="row">
    <div class="card">
      <h2>你本周点歌（{{ me_name }}）</h2>
      {% if me_week and me_week|length > 0 %}
        <ol>
          {% for s in me_week %}
            <li>{{ s }}</li>
          {% endfor %}
        </ol>
      {% else %}
        <div class="muted">你这周还没提交～</div>
      {% endif %}
    </div>

    <div class="card">
      <h2>对方本周点歌（{{ other_name }}）</h2>
      {% if other_week and other_week|length > 0 %}
        <ol>
          {% for s in other_week %}
            <li>{{ s }}</li>
          {% endfor %}
        </ol>
      {% else %}
        <div class="muted">对方这周还没提交～</div>
      {% endif %}
    </div>
  </div>

  <div class="row">
    <div class="card">
      <h2>你的 Top 3（按出现次数）</h2>
      <table>
        <tr><th>歌名</th><th>次数</th></tr>
        {% for song, cnt in top_me %}
          <tr><td>{{ song }}</td><td>{{ cnt }}</td></tr>
        {% endfor %}
        {% if not top_me or top_me|length == 0 %}
          <tr><td class="muted">暂无数据</td><td class="muted">-</td></tr>
        {% endif %}
      </table>
    </div>

    <div class="card">
      <h2>对方 Top 3（按出现次数）</h2>
      <table>
        <tr><th>歌名</th><th>次数</th></tr>
        {% for song, cnt in top_other %}
          <tr><td>{{ song }}</td><td>{{ cnt }}</td></tr>
        {% endfor %}
        {% if not top_other or top_other|length == 0 %}
          <tr><td class="muted">暂无数据</td><td class="muted">-</td></tr>
        {% endif %}
      </table>
    </div>
  </div>

  <div class="card">
    <h2>本周提交情况（所有记录）</h2>
    <table>
      <tr><th>用户</th><th>歌名</th><th>提交时间</th></tr>
      {% for slot, song, ts in this_week %}
        <tr>
          <td>{{ names.get(slot, slot) }}</td>
          <td>{{ song }}</td>
          <td>{{ ts }}</td>
        </tr>
      {% endfor %}
      {% if not this_week or this_week|length == 0 %}
        <tr><td class="muted">暂无提交</td><td class="muted">-</td><td class="muted">-</td></tr>
      {% endif %}
    </table>
  </div>

</body>
</html>
"""

# -------------------------
# Database: Postgres on Render (DATABASE_URL), SQLite locally
# -------------------------
BASE_DIR = os.path.dirname(__file__)
SQLITE_PATH = os.path.join(BASE_DIR, "mayday_requests.db")

def is_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))

def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Render provides postgres://... which psycopg2 accepts
        return psycopg2.connect(db_url)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ph() -> str:
    # placeholder token: %s for postgres, ? for sqlite
    return "%s" if is_postgres() else "?"

def execute(conn, sql: str, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur

def executemany(conn, sql: str, seq_params):
    cur = conn.cursor()
    cur.executemany(sql, seq_params)
    return cur

def init_db():
    conn = get_conn()
    try:
        if is_postgres():
            execute(conn, """
              CREATE TABLE IF NOT EXISTS submissions (
                id BIGSERIAL PRIMARY KEY,
                slot TEXT NOT NULL,
                week_id TEXT NOT NULL,
                song TEXT NOT NULL,
                created_at TEXT NOT NULL
              )
            """)
            execute(conn, """
              CREATE TABLE IF NOT EXISTS profiles (
                slot TEXT PRIMARY KEY,
                name TEXT NOT NULL
              )
            """)
            execute(conn, "CREATE INDEX IF NOT EXISTS idx_slot_week ON submissions(slot, week_id)")
            execute(conn, "CREATE INDEX IF NOT EXISTS idx_slot_song ON submissions(slot, song)")
        else:
            execute(conn, """
              CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot TEXT NOT NULL,
                week_id TEXT NOT NULL,
                song TEXT NOT NULL,
                created_at TEXT NOT NULL
              )
            """)
            execute(conn, """
              CREATE TABLE IF NOT EXISTS profiles (
                slot TEXT PRIMARY KEY,
                name TEXT NOT NULL
              )
            """)
            execute(conn, "CREATE INDEX IF NOT EXISTS idx_slot_week ON submissions(slot, week_id)")
            execute(conn, "CREATE INDEX IF NOT EXISTS idx_slot_song ON submissions(slot, song)")

        conn.commit()
    finally:
        conn.close()

# ✅ 启动时确保表存在（Render / 本地都能用）
init_db()

def current_week_id() -> str:
    y, w, _ = date.today().isocalendar()
    return f"{y}-W{w:02d}"

def normalize_song(s: str) -> str:
    return " ".join((s or "").strip().split())

def normalize_name(s: str) -> str:
    return (s or "").strip()

def label_for(slot: str) -> str:
    return "用户一" if slot == "user1" else "用户二"

def get_names() -> dict:
    conn = get_conn()
    try:
        cur = execute(conn, "SELECT slot, name FROM profiles")
        rows = cur.fetchall()
        d = {slot: name for slot, name in rows}
    finally:
        conn.close()

    for s in SLOTS:
        d.setdefault(s, label_for(s))
    return d

def set_name(slot: str, name: str):
    conn = get_conn()
    try:
        if is_postgres():
            execute(conn, """
              INSERT INTO profiles(slot, name) VALUES(%s, %s)
              ON CONFLICT(slot) DO UPDATE SET name = EXCLUDED.name
            """, (slot, name))
        else:
            execute(conn, """
              INSERT INTO profiles(slot, name) VALUES(?, ?)
              ON CONFLICT(slot) DO UPDATE SET name = excluded.name
            """, (slot, name))
        conn.commit()
    finally:
        conn.close()

def top3_for(slot: str):
    conn = get_conn()
    try:
        token = ph()
        sql = f"""
          SELECT song, COUNT(*) as cnt
          FROM submissions
          WHERE slot = {token}
          GROUP BY song
          ORDER BY cnt DESC, song ASC
          LIMIT 3
        """
        cur = execute(conn, sql, (slot,))
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()

def this_week_rows(week_id: str):
    conn = get_conn()
    try:
        token = ph()
        sql = f"""
          SELECT slot, song, created_at
          FROM submissions
          WHERE week_id = {token}
          ORDER BY created_at DESC
          LIMIT 200
        """
        cur = execute(conn, sql, (week_id,))
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()

def week_songs_for(slot: str, week_id: str):
    conn = get_conn()
    try:
        token = ph()
        sql = f"""
          SELECT song
          FROM submissions
          WHERE slot = {token} AND week_id = {token}
          ORDER BY id ASC
        """
        cur = execute(conn, sql, (slot, week_id))
        songs = [r[0] for r in cur.fetchall()]
        return songs
    finally:
        conn.close()

@app.get("/login")
def login_get():
    return render_template_string(LOGIN_PAGE, error=None)

@app.post("/login")
def login_post():
    slot = (request.form.get("slot") or "").strip()
    name = normalize_name(request.form.get("name"))

    if slot not in SLOTS:
        return render_template_string(LOGIN_PAGE, error="请选择用户一或用户二。")
    if not name:
        return render_template_string(LOGIN_PAGE, error="昵称不能为空。")
    if len(name) > 64:
        return render_template_string(LOGIN_PAGE, error="昵称太长啦（最多 64 个字符）。")

    session["slot"] = slot
    set_name(slot, name)

    return redirect(url_for("home"))

@app.get("/logout")
def logout():
    session.pop("slot", None)
    return redirect(url_for("login_get"))

@app.get("/")
def home():
    if "slot" not in session:
        return redirect(url_for("login_get"))

    me = session["slot"]
    other = "user2" if me == "user1" else "user1"
    week_id = current_week_id()

    names = get_names()
    return render_template_string(
        PAGE,
        week_id=week_id,
        names=names,
        me_name=names.get(me, label_for(me)),
        other_name=names.get(other, label_for(other)),
        me_label=label_for(me),
        other_label=label_for(other),
        top_me=top3_for(me),
        top_other=top3_for(other),
        me_week=week_songs_for(me, week_id),
        other_week=week_songs_for(other, week_id),
        this_week=this_week_rows(week_id),
    )

@app.post("/submit")
def submit():
    if "slot" not in session:
        return redirect(url_for("login_get"))

    slot = session["slot"]

    songs = [
        normalize_song(request.form.get("song1")),
        normalize_song(request.form.get("song2")),
        normalize_song(request.form.get("song3")),
    ]

    if any(not s for s in songs):
        return "Songs cannot be empty", 400
    if len(set(songs)) != 3:
        return "Three songs must be distinct", 400

    week_id = current_week_id()
    now = datetime.now().isoformat(timespec="seconds")

    conn = get_conn()
    try:
        token = ph()
        # 本周覆盖：先删旧的再写新的三首
        execute(conn, f"DELETE FROM submissions WHERE slot = {token} AND week_id = {token}", (slot, week_id))

        if is_postgres():
            executemany(
                conn,
                "INSERT INTO submissions(slot, week_id, song, created_at) VALUES(%s,%s,%s,%s)",
                [(slot, week_id, s, now) for s in songs]
            )
        else:
            executemany(
                conn,
                "INSERT INTO submissions(slot, week_id, song, created_at) VALUES(?,?,?,?)",
                [(slot, week_id, s, now) for s in songs]
            )

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("home"))

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

