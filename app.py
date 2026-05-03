from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, emit, join_room
import sqlite3, bcrypt, uuid

app = Flask(__name__)
app.secret_key = "secret"
socketio = SocketIO(app, async_mode="threading")

# ===== DATABASE =====
def db():
    con = sqlite3.connect("chat.db", check_same_thread=False, timeout=10)
    con.execute("PRAGMA journal_mode=WAL;")
    return con

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS friends (u1 TEXT, u2 TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS requests (sender TEXT, receiver TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS messages (u1 TEXT, u2 TEXT, sender TEXT, text TEXT, image TEXT)")

    con.commit()
    con.close()

init_db()

# ===== ROUTE =====
@app.route('/')
def home():
    return render_template("login.html")

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect('/')
    return render_template("chat.html", user=session['user'])

# ===== AUTH =====
@app.route('/register', methods=['POST'])
def register():
    try:
        u = request.form['username']
        p = request.form['password']

        con = db()
        cur = con.cursor()

        cur.execute("SELECT * FROM users WHERE username=?", (u,))
        if cur.fetchone():
            return "User tồn tại"

        hashed = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

        cur.execute("INSERT INTO users VALUES (?,?)", (u, hashed))
        con.commit()
        con.close()

        return "OK"
    except Exception as e:
        print(e)
        return "Lỗi server"

@app.route('/login', methods=['POST'])
def login():
    try:
        u = request.form['username']
        p = request.form['password']

        con = db()
        cur = con.cursor()

        cur.execute("SELECT password FROM users WHERE username=?", (u,))
        row = cur.fetchone()
        con.close()

        if row and bcrypt.checkpw(p.encode(), row[0].encode()):
            session['user'] = u
            return "OK"

        return "Sai tài khoản"
    except Exception as e:
        print(e)
        return "Lỗi server"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ===== FRIEND =====
@app.route('/send_request', methods=['POST'])
def send_request():
    me = session['user']
    to = request.form['to']

    con = db()
    cur = con.cursor()

    cur.execute("SELECT * FROM requests WHERE sender=? AND receiver=?", (me, to))
    if cur.fetchone():
        return "Đã gửi rồi"

    cur.execute("INSERT INTO requests VALUES (?,?)", (me, to))
    con.commit()
    con.close()

    return "Đã gửi"

@app.route('/requests')
def get_requests():
    me = session['user']

    con = db()
    cur = con.cursor()
    cur.execute("SELECT sender FROM requests WHERE receiver=?", (me,))
    data = [r[0] for r in cur.fetchall()]
    con.close()

    return data

@app.route('/accept', methods=['POST'])
def accept():
    me = session['user']
    u = request.form['user']

    con = db()
    cur = con.cursor()

    cur.execute("INSERT INTO friends VALUES (?,?)", (me, u))
    cur.execute("INSERT INTO friends VALUES (?,?)", (u, me))
    cur.execute("DELETE FROM requests WHERE sender=? AND receiver=?", (u, me))

    con.commit()
    con.close()

    return "OK"

@app.route('/friends')
def friends():
    me = session['user']

    con = db()
    cur = con.cursor()

    cur.execute("SELECT u2 FROM friends WHERE u1=?", (me,))
    data = [r[0] for r in cur.fetchall()]
    con.close()

    return data

# ===== MESSAGES =====
@app.route('/messages/<user>')
def messages(user):
    me = session['user']

    con = db()
    cur = con.cursor()

    cur.execute("""
    SELECT sender, text, image FROM messages
    WHERE (u1=? AND u2=?) OR (u1=? AND u2=?)
    """, (me, user, user, me))

    data = [{"user":r[0], "text":r[1], "image":r[2]} for r in cur.fetchall()]
    con.close()

    return data

# ===== SOCKET =====
@socketio.on("join")
def join(data):
    room = "_".join(sorted([data['u1'], data['u2']]))
    join_room(room)

@socketio.on("send")
def send(data):
    me = session['user']
    to = data['to']
    text = data.get('text', '')
    image = data.get('image', '')

    # BOT PYTHON
    if text.startswith("py "):
        try:
            code = text[3:]
            result = str(eval(code))
            emit("msg", {"user":"🤖 Bot", "text":result}, room=request.sid)
        except:
            emit("msg", {"user":"🤖 Bot", "text":"Lỗi code"}, room=request.sid)
        return

    con = db()
    cur = con.cursor()

    cur.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (me, to, me, text, image))
    con.commit()
    con.close()

    room = "_".join(sorted([me, to]))
    emit("msg", {"user":me, "text":text, "image":image}, room=room)

# ===== RUN =====
if __name__ == "__main__":
    socketio.run(app)
