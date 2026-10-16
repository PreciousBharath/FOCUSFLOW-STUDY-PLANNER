"""FocusFlow — Smart study planner: drag-and-drop Kanban, animated Pomodoro focus timer, streaks & analytics.
Run:  python app.py   →  http://127.0.0.1:5000   (demo: demo@example.com / Demo@1234)
"""
import random
from datetime import date, datetime, timedelta

from flask import g, jsonify, render_template, request

from core import create_app, execute, login_required, now, query

UI = dict(
    name="FocusFlow", short="Smart Study Planner", icon="🎯", accent1="#FF6B6B", accent2="#845EF7", home="board",
    tagline="Plan smarter, focus deeper. Kanban tasks, a beautiful Pomodoro timer and analytics that keep your streak alive.",
    hero='Deep focus, <span class="gradient-text">every single day.</span>', badge="Productivity reimagined",
    features=[("bi-kanban", "Drag & drop Kanban", "To-do → Doing → Done with smooth animations"),
              ("bi-stopwatch", "Pomodoro timer", "Animated focus ring, breaks, sounds & notifications"),
              ("bi-fire", "Streaks & heatmap", "GitHub-style activity calendar and weekly insights")],
    float=['🔥 <b>12-day</b> focus streak', '⏱️ <b class="gradient-text">25:00</b> Deep work session'],
    nav=[("Task Board", "board", "bi-kanban"), ("Focus Timer", "focus", "bi-stopwatch"), ("Analytics", "stats", "bi-bar-chart-line")],
    search_hint="Search tasks…", promo_title="Smart plan", promo="Tasks are ranked by priority, deadline and remaining effort.",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL, subject TEXT DEFAULT 'General', priority INTEGER DEFAULT 2, due TEXT,
    status TEXT DEFAULT 'todo' CHECK(status IN ('todo','doing','done')), est_pomos INTEGER DEFAULT 2, done_pomos INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT);
CREATE TABLE IF NOT EXISTS focus_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL, minutes INTEGER NOT NULL, subject TEXT, ended_at TEXT NOT NULL);
"""
SUBJECTS = {"Machine Learning": "#845EF7", "Python": "#3DA9FC", "Mathematics": "#FF6B6B", "Data Analysis": "#2CB67D",
            "Deep Learning": "#F7B32B", "Projects": "#E85D75", "General": "#9AA0C3"}


def seed_demo(uid):
    rng = random.Random(3)
    today = date.today()
    tasks = [("Revise gradient descent & loss functions", "Machine Learning", 3, 1, "doing", 4, 2),
             ("Finish Pandas groupby exercises", "Data Analysis", 2, 3, "todo", 3, 0),
             ("Build CNN for image classification", "Deep Learning", 3, 5, "todo", 6, 1),
             ("Linear algebra — eigenvalues", "Mathematics", 2, 2, "todo", 2, 0),
             ("Python OOP mini-project", "Python", 1, 9, "todo", 3, 0),
             ("Write project report introduction", "Projects", 2, 4, "doing", 2, 1),
             ("Watch lecture: Transformers", "Deep Learning", 1, 6, "todo", 2, 0),
             ("Matplotlib dashboard practice", "Data Analysis", 1, -2, "done", 2, 2),
             ("Probability quiz prep", "Mathematics", 3, -1, "done", 3, 3),
             ("List comprehension drills", "Python", 1, -4, "done", 1, 1)]
    for i, (t, s, p, d, st, e, dp) in enumerate(tasks):
        execute("INSERT INTO tasks(user_id,title,subject,priority,due,status,est_pomos,done_pomos,position,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (uid, t, s, p, (today + timedelta(days=d)).isoformat(), st, e, dp, i, now() if st == "done" else None))
    for d in range(70, -1, -1):
        day = today - timedelta(days=d)
        if d > 12 and rng.random() < .35:
            continue
        for _ in range(rng.randint(1, 5)):
            execute("INSERT INTO focus_sessions(user_id,minutes,subject,ended_at) VALUES(?,?,?,?)",
                    (uid, rng.choice([25, 25, 25, 50, 15]), rng.choice(list(SUBJECTS)[:6]),
                     f"{day.isoformat()} {rng.randint(8, 22):02d}:{rng.randint(0, 59):02d}:00"))


def on_register(uid):
    execute("INSERT INTO tasks(user_id,title,subject,priority,due,est_pomos) VALUES(?,?,?,?,?,?)",
            (uid, "👋 Drag me to 'Doing' to get started", "General", 2, date.today().isoformat(), 1))


app = create_app(__name__, UI, SCHEMA, seed_demo=seed_demo, on_register=on_register)


def smart_score(t):
    """Higher = do sooner. Priority + deadline urgency + remaining effort."""
    days = (datetime.strptime(t["due"], "%Y-%m-%d").date() - date.today()).days if t["due"] else 14
    urgency = 10 if days < 0 else max(0, 7 - days) * 1.4
    remaining = max(0, t["est_pomos"] - t["done_pomos"])
    return round(t["priority"] * 2.5 + urgency + remaining * 0.6, 1)


def stats_for(uid):
    rows = query("SELECT minutes, subject, substr(ended_at,1,10) d, CAST(substr(ended_at,12,2) AS INTEGER) h FROM focus_sessions WHERE user_id=?", (uid,))
    by_day, by_subj, by_hour = {}, {}, [0] * 24
    for r in rows:
        by_day[r["d"]] = by_day.get(r["d"], 0) + r["minutes"]
        by_subj[r["subject"] or "General"] = by_subj.get(r["subject"] or "General", 0) + r["minutes"]
        by_hour[r["h"]] += r["minutes"]
    today = date.today()
    streak, d = 0, today
    if today.isoformat() not in by_day:
        d = today - timedelta(days=1)
    while d.isoformat() in by_day:
        streak += 1
        d -= timedelta(days=1)
    best, cur = 0, 0
    for i in range(365, -1, -1):
        cur = cur + 1 if (today - timedelta(days=i)).isoformat() in by_day else 0
        best = max(best, cur)
    week = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    heat = [{"d": (today - timedelta(days=i)).isoformat(), "m": by_day.get((today - timedelta(days=i)).isoformat(), 0)} for i in range(119, -1, -1)]
    tasks = query("SELECT status FROM tasks WHERE user_id=?", (uid,))
    return dict(total_hours=round(sum(by_day.values()) / 60, 1), today_min=by_day.get(today.isoformat(), 0), streak=streak, best=best,
                sessions=len(rows), done=sum(t["status"] == "done" for t in tasks), total_tasks=len(tasks),
                week={"labels": [w.strftime("%a") for w in week], "data": [by_day.get(w.isoformat(), 0) for w in week]},
                subjects=dict(sorted(by_subj.items(), key=lambda kv: -kv[1])), hours=by_hour, heat=heat,
                peak_hour=max(range(24), key=lambda h: by_hour[h]) if rows else None)


@app.route("/board")
@login_required
def board():
    return render_template("board.html", SUBJECTS=SUBJECTS, s=stats_for(g.user["id"]), page_title="Task Board")


@app.route("/focus")
@login_required
def focus():
    tasks = query("SELECT * FROM tasks WHERE user_id=? AND status!='done'", (g.user["id"],))
    tasks.sort(key=smart_score, reverse=True)
    return render_template("focus.html", tasks=tasks, s=stats_for(g.user["id"]), SUBJECTS=SUBJECTS, page_title="Focus Timer")


@app.route("/stats")
@login_required
def stats():
    return render_template("stats.html", s=stats_for(g.user["id"]), SUBJECTS=SUBJECTS, page_title="Analytics")


# ---------------------------------------------------------------- API
@app.get("/api/tasks")
@login_required
def api_tasks():
    rows = query("SELECT * FROM tasks WHERE user_id=? ORDER BY position, id", (g.user["id"],))
    for r in rows:
        r["score"] = smart_score(r)
    return jsonify(rows)


@app.post("/api/tasks")
@login_required
def api_task_add():
    d = request.get_json(force=True)
    title = str(d.get("title", "")).strip()[:140]
    if not title:
        return jsonify(error="Title is required"), 400
    tid = execute("INSERT INTO tasks(user_id,title,subject,priority,due,est_pomos,status) VALUES(?,?,?,?,?,?,?)",
                  (g.user["id"], title, d.get("subject") if d.get("subject") in SUBJECTS else "General",
                   min(3, max(1, int(d.get("priority", 2)))), d.get("due") or None, min(20, max(1, int(d.get("est_pomos", 2)))), "todo"))
    t = query("SELECT * FROM tasks WHERE id=?", (tid,), one=True)
    t["score"] = smart_score(t)
    return jsonify(t), 201


@app.patch("/api/tasks/<int:tid>")
@login_required
def api_task_update(tid):
    d = request.get_json(force=True)
    t = query("SELECT * FROM tasks WHERE id=? AND user_id=?", (tid, g.user["id"]), one=True)
    if not t:
        return jsonify(error="Not found"), 404
    status = d.get("status", t["status"])
    if status not in ("todo", "doing", "done"):
        return jsonify(error="Bad status"), 400
    completed = now() if status == "done" and t["status"] != "done" else (t["completed_at"] if status == "done" else None)
    execute("UPDATE tasks SET status=?, position=?, completed_at=? WHERE id=?", (status, int(d.get("position", t["position"])), completed, tid))
    if "order" in d:  # full column ordering from drag & drop
        for i, oid in enumerate(d["order"]):
            execute("UPDATE tasks SET position=? WHERE id=? AND user_id=?", (i, int(oid), g.user["id"]))
    return jsonify(ok=True, celebrate=status == "done" and t["status"] != "done")


@app.delete("/api/tasks/<int:tid>")
@login_required
def api_task_delete(tid):
    execute("DELETE FROM tasks WHERE id=? AND user_id=?", (tid, g.user["id"]))
    return jsonify(ok=True)


@app.post("/api/sessions")
@login_required
def api_session():
    d = request.get_json(force=True)
    minutes = int(d.get("minutes", 0))
    if not 1 <= minutes <= 180:
        return jsonify(error="Invalid duration"), 400
    task = query("SELECT * FROM tasks WHERE id=? AND user_id=?", (d.get("task_id"), g.user["id"]), one=True) if d.get("task_id") else None
    execute("INSERT INTO focus_sessions(user_id,task_id,minutes,subject,ended_at) VALUES(?,?,?,?,?)",
            (g.user["id"], task["id"] if task else None, minutes, task["subject"] if task else "General", now()))
    if task:
        execute("UPDATE tasks SET done_pomos=done_pomos+1, status=CASE WHEN status='todo' THEN 'doing' ELSE status END WHERE id=?", (task["id"],))
    s = stats_for(g.user["id"])
    return jsonify(ok=True, today_min=s["today_min"], streak=s["streak"])


if __name__ == "__main__":
    app.run(debug=True)
