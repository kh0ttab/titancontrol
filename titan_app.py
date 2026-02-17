import streamlit as st
import pandas as pd
import datetime
import os
import time
import sqlite3
import hashlib
from urllib.parse import quote

# --- SAFETY: GEMINI IMPORT ---
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Titan Control OS",
    page_icon="🦁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE SETUP ---
DB_FILE = "titan.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    name TEXT,
                    role TEXT,
                    avatar TEXT,
                    is_admin BOOLEAN
                )''')
    
    # 2. Tasks
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    assignee TEXT,
                    company TEXT,
                    category TEXT,
                    priority TEXT,
                    status TEXT,
                    planned_date TEXT,
                    timer_start TEXT,
                    act_time REAL,
                    notes TEXT,
                    rating INTEGER,
                    feedback TEXT
                )''')
    
    # DB Migration
    try: c.execute("ALTER TABLE tasks ADD COLUMN company TEXT")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN timer_start TEXT")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN rating INTEGER")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN feedback TEXT")
    except: pass
                
    # 3. Shipments
    c.execute('''CREATE TABLE IF NOT EXISTS shipments (
                    id TEXT PRIMARY KEY,
                    date TEXT,
                    am TEXT,
                    dest TEXT,
                    skus TEXT,
                    qty INTEGER,
                    status TEXT,
                    tracking TEXT
                )''')

    # 4. Work Logs
    c.execute('''CREATE TABLE IF NOT EXISTS work_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    event_type TEXT,
                    timestamp TEXT
                )''')
    
    # 5. Companies
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
                    name TEXT PRIMARY KEY
                )''')

    # 6. Inventory
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    sku TEXT PRIMARY KEY,
                    name TEXT,
                    stock INTEGER,
                    location TEXT
                )''')

    # 7. SOPs
    c.execute('''CREATE TABLE IF NOT EXISTS sops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    category TEXT
                )''')

    # 8. Task Comments (New)
    c.execute('''CREATE TABLE IF NOT EXISTS task_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    username TEXT,
                    comment TEXT,
                    timestamp TEXT
                )''')
    
    # Seed Default Data
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('admin', pwd_hash, 'Big Boss', 'CEO', '🦁', True))
    
    c.execute("SELECT * FROM users WHERE username = 'alex'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('alex', pwd_hash, 'Alex', 'Account Manager', '👨‍💻', False))

    c.execute("SELECT * FROM users WHERE username = 'sarah'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('sarah', pwd_hash, 'Sarah', 'Researcher', '🔎', False))

    c.execute("SELECT * FROM users WHERE username = 'mike'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('mike', pwd_hash, 'Mike', 'Warehouse Labour', '📦', False))
    
    # Default Companies & Inventory
    c.execute("INSERT OR IGNORE INTO companies VALUES ('Internal')")
    c.execute("INSERT OR IGNORE INTO companies VALUES ('Client A')")
    c.execute("INSERT OR IGNORE INTO inventory VALUES ('SKU-001', 'Wireless Mouse', 500, 'A1')")
    
    c.execute("SELECT * FROM sops")
    if not c.fetchone():
        c.execute("INSERT INTO sops (title, content, category) VALUES (?, ?, ?)", 
                 ('How to Pack Fragile Items', '1. Wrap in bubble wrap (2 layers).\n2. Use double-walled box.', 'Logistics'))
        
    conn.commit()
    conn.close()

init_db()

# --- BACKEND FUNCTIONS ---
def get_db():
    return sqlite3.connect(DB_FILE)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    conn = get_db()
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, pwd_hash))
    user = c.fetchone()
    conn.close()
    if user:
        return {"username": user[0], "name": user[2], "role": user[3], "avatar": user[4], "is_admin": user[5]}
    return None

def create_user(username, password, name, role, is_admin):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  (username, hash_password(password), name, role, '👤', is_admin))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_users():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM users", conn)
    conn.close()
    return df

def delete_user(username):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

# --- TIME CLOCK FUNCTIONS ---
def log_work_event(username, event_type):
    conn = get_db()
    conn.execute("INSERT INTO work_logs (username, event_type, timestamp) VALUES (?, ?, ?)",
                 (username, event_type, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_last_work_event(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT event_type, timestamp FROM work_logs WHERE username=? ORDER BY id DESC LIMIT 1", (username,))
    res = c.fetchone()
    conn.close()
    return res

def get_live_workers():
    users = get_all_users()
    active_workers = []
    for _, u in users.iterrows():
        last = get_last_work_event(u['username'])
        if last and last[0] == 'CLOCK_IN':
            active_workers.append({'name': u['name'], 'role': u['role'], 'since': last[1]})
    return active_workers

def get_work_logs():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM work_logs ORDER BY id DESC", conn)
    conn.close()
    return df

# --- COMPANY & INVENTORY FUNCTIONS ---
def get_companies():
    conn = get_db()
    df = pd.read_sql("SELECT name FROM companies", conn)
    conn.close()
    return df['name'].tolist()

def add_company(name):
    conn = get_db()
    try:
        conn.execute("INSERT INTO companies VALUES (?)", (name,))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_inventory():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()
    return df

def add_inventory(sku, name, stock, location):
    conn = get_db()
    try:
        conn.execute("INSERT INTO inventory VALUES (?, ?, ?, ?)", (sku, name, stock, location))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def get_sops():
    conn = get_db()
    df = pd.read_sql("SELECT * FROM sops", conn)
    conn.close()
    return df

def add_sop(title, content, category):
    conn = get_db()
    conn.execute("INSERT INTO sops (title, content, category) VALUES (?, ?, ?)", (title, content, category))
    conn.commit()
    conn.close()

# --- COMMENT FUNCTIONS ---
def add_comment(task_id, username, comment):
    conn = get_db()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("INSERT INTO task_comments (task_id, username, comment, timestamp) VALUES (?, ?, ?, ?)",
                 (task_id, username, comment, ts))
    conn.commit()
    conn.close()

def get_comments(task_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM task_comments WHERE task_id=? ORDER BY id ASC", (task_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# --- CALENDAR HELPERS ---
def create_gcal_link(title, date_str, desc=""):
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        start = dt.replace(hour=9, minute=0).strftime("%Y%m%dT%H%M%S")
        end = dt.replace(hour=10, minute=0).strftime("%Y%m%dT%H%M%S")
        base = "https://www.google.com/calendar/render?action=TEMPLATE"
        link = f"{base}&text={quote(title)}&dates={start}/{end}&details={quote(desc)}"
        return link
    except:
        return "#"

# --- TASK FUNCTIONS ---
def get_tasks():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tasks ORDER BY id DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def add_task(title, assignee, company, category):
    conn = get_db()
    conn.execute("INSERT INTO tasks (title, assignee, company, category, priority, status, planned_date, act_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (title, assignee, company, category, "Medium", "To Do", str(datetime.date.today()), 0.0))
    conn.commit()
    conn.close()

def update_task(task_id, status, assignee, act_time):
    conn = get_db()
    conn.execute("UPDATE tasks SET status=?, assignee=?, act_time=? WHERE id=?", (status, assignee, act_time, task_id))
    conn.commit()
    conn.close()

def rate_task(task_id, rating, feedback):
    conn = get_db()
    conn.execute("UPDATE tasks SET rating=?, feedback=? WHERE id=?", (rating, feedback, task_id))
    conn.commit()
    conn.close()

def toggle_task_timer(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT timer_start, act_time FROM tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    
    if row:
        start_ts, current_act = row
        current_act = current_act if current_act else 0.0
        
        if start_ts: # Stop
            start_dt = datetime.datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
            diff_hours = (datetime.datetime.now() - start_dt).total_seconds() / 3600.0
            new_act = current_act + diff_hours
            c.execute("UPDATE tasks SET timer_start=NULL, act_time=?, status='Done' WHERE id=?", (new_act, task_id))
            st.toast(f"Timer Stopped. Added {diff_hours:.2f} hours.")
        else: # Start
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("UPDATE tasks SET timer_start=?, status='In Progress' WHERE id=?", (now_str, task_id))
            st.toast("Timer Started!")
    conn.commit()
    conn.close()

# --- SHIPMENT FUNCTIONS ---
def get_shipments():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM shipments ORDER BY date DESC").fetchall()]
    conn.close()
    return rows

def add_shipment(s_id, date, am, dest, skus, qty):
    conn = get_db()
    conn.execute("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (s_id, str(date), am, dest, skus, qty, "New", ""))
    conn.commit()
    conn.close()

def update_shipment_details(s_id, dest, skus, qty, status):
    conn = get_db()
    conn.execute("UPDATE shipments SET dest=?, skus=?, qty=?, status=? WHERE id=?", 
                 (dest, skus, qty, status, s_id))
    conn.commit()
    conn.close()

# --- GEMINI AI ---
api_key = st.sidebar.text_input("🔑 Gemini API Key", type="password") if "authenticated" in st.session_state and st.session_state.authenticated else None
if api_key and AI_AVAILABLE:
    genai.configure(api_key=api_key)

def ask_gemini(prompt, context=""):
    if not AI_AVAILABLE: return "Library not installed."
    if not api_key: return "Enter API Key."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
        return model.generate_content(f"Titan AI Context: {context}. User: {prompt}").text
    except Exception as e: return f"Error: {e}"

# --- CSS STYLING (LIQUID GLASS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    .stApp {
        background-color: #09090b;
        background-image: 
            radial-gradient(at 0% 0%, rgba(76, 29, 149, 0.4) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(236, 72, 153, 0.4) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.4) 0px, transparent 50%),
            radial-gradient(at 0% 100%, rgba(16, 185, 129, 0.4) 0px, transparent 50%);
        background-attachment: fixed;
        background-size: cover;
        font-family: 'Outfit', sans-serif;
        color: white;
    }

    [data-testid="stSidebar"] {
        background: rgba(9, 9, 11, 0.7);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255,255,255,0.1);
    }

    .titan-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(16px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 15px;
        transition: transform 0.2s;
    }
    .titan-card:hover {
        transform: translateY(-3px);
        border-color: rgba(255, 255, 255, 0.25);
    }

    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        background-color: rgba(0, 0, 0, 0.4) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 8px !important;
    }
    
    div.stButton > button {
        background: linear-gradient(90deg, #ec4899, #8b5cf6);
        border: none;
        color: white;
        font-weight: 600;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        box-shadow: 0 0 15px rgba(236, 72, 153, 0.5);
    }
    
    .status-badge {
        padding: 4px 10px; border-radius:12px; font-weight:bold; font-size:12px; text-transform:uppercase;
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def safe_rerun():
    time.sleep(0.1)
    st.rerun()

def get_efficiency_badge(task):
    if task["status"] == "Done":
        return '<span class="badge" style="background:#10b98120; color:#4ade80;">Done</span>'
    return '<span class="badge" style="background:#3b82f620; color:#60a5fa;">Active</span>'

def render_metric_card(icon, gradient, value, label, sub):
    st.markdown(f"""
    <div class="titan-card">
        <div style="width:48px; height:48px; border-radius:14px; display:flex; align-items:center; justify-content:center; font-size:24px; background:{gradient}; color:white; margin-bottom:15px; box-shadow:inset 0 0 0 1px rgba(255,255,255,0.1);">
            {icon}
        </div>
        <div style="font-size:32px; font-weight:700; background:linear-gradient(135deg, #ffffff 0%, #a5b4fc 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:5px;">{value}</div>
        <div style="font-size:14px; color:rgba(255,255,255,0.7); font-weight:500; text-transform:uppercase;">{label}</div>
        <div style="font-size:12px; color:rgba(255,255,255,0.5);">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION FLOW ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 40px; text-align: center;">
            <h1 style="background: linear-gradient(to right, #ec4899, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">TITAN CONTROL</h1>
            <p style="color: #a1a1aa;">Secure Enterprise Access</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("LOGIN", type="primary", use_container_width=True):
                user = verify_user(u, p)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success("Authenticated")
                    safe_rerun()
                else:
                    st.error("Access Denied")
        st.info("Default: admin / 123")

if not st.session_state.authenticated:
    login()
else:
    user = st.session_state.user
    
    # --- SIDEBAR ---
    st.sidebar.markdown("<h2>TITAN OS</h2>", unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); border-radius: 12px; padding: 15px; border: 1px solid rgba(255,255,255,0.1);">
        <div style="display:flex; align-items:center; gap:10px;">
            <div style="font-size:28px;">{user['avatar']}</div>
            <div>
                <div style="font-weight:bold; font-size:15px;">{user['name']}</div>
                <div style="font-size:11px; color:#a1a1aa; text-transform:uppercase;">{user['role']}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Time Clock
    st.sidebar.markdown("### ⏱ Time Clock")
    last_event = get_last_work_event(user['username'])
    is_working = last_event and last_event[0] == 'CLOCK_IN'
    
    if is_working:
        st.sidebar.success(f"🟢 Working since {last_event[1][11:16]}")
        if st.sidebar.button("CLOCK OUT"):
            log_work_event(user['username'], 'CLOCK_OUT')
            st.success("Shift Ended")
            safe_rerun()
    else:
        st.sidebar.warning("⚪ Currently Offline")
        if st.sidebar.button("CLOCK IN"):
            log_work_event(user['username'], 'CLOCK_IN')
            st.success("Shift Started")
            safe_rerun()

    st.sidebar.markdown("---")
    nav_opts = ["Dashboard", "My Desk", "Team Calendar", "3PL Logistics", "Team & Reports", "Inventory & SOPs", "AI Assistant 🤖"]
    page = st.sidebar.radio("NAVIGATION", nav_opts)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("LOGOUT"):
        st.session_state.authenticated = False
        safe_rerun()

    # --- PAGE: DASHBOARD ---
    if page == "Dashboard":
        st.markdown("# Executive Overview")
        
        tasks = get_tasks()
        
        # Key Metrics Calculation
        total = len(tasks)
        in_progress_tasks = [t for t in tasks if t['status'] == 'In Progress']
        in_progress_count = len(in_progress_tasks)
        todo_tasks = [t for t in tasks if t['status'] == 'To Do']
        todo_count = len(todo_tasks)
        done_tasks = [t for t in tasks if t['status'] == 'Done']
        done_count = len(done_tasks)
        
        completion_rate = int((done_count / total * 100)) if total > 0 else 0

        # Session state for filter
        if "dashboard_filter" not in st.session_state:
            st.session_state.dashboard_filter = "In Progress"

        c1, c2, c3, c4 = st.columns(4)
        
        # Helper to render card and button
        def metric_button(col, icon, grad, val, lbl, sub, filter_key):
            with col:
                render_metric_card(icon, grad, val, lbl, sub)
                if st.button(f"View {lbl}", key=f"btn_{filter_key}", use_container_width=True):
                    st.session_state.dashboard_filter = filter_key
                    safe_rerun()

        metric_button(c1, "⚡", "linear-gradient(135deg, #3b82f6, #06b6d4)", str(total), "Total Tasks", "All Time", "All")
        metric_button(c2, "🔥", "linear-gradient(135deg, #f59e0b, #fbbf24)", str(in_progress_count), "In Progress", "Happening Now", "In Progress")
        metric_button(c3, "📋", "linear-gradient(135deg, #8b5cf6, #d946ef)", str(todo_count), "To Do", "Backlog", "To Do")
        metric_button(c4, "✅", "linear-gradient(135deg, #10b981, #34d399)", f"{completion_rate}%", "Completion", "Efficiency", "Done")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- DRILL DOWN SECTION ---
        st.markdown(f"### 🔎 Task Drilldown: {st.session_state.dashboard_filter}")
        
        # Filter Logic
        if st.session_state.dashboard_filter == "All":
            filtered_tasks = tasks
        elif st.session_state.dashboard_filter == "Done":
             filtered_tasks = done_tasks
        else:
            filtered_tasks = [t for t in tasks if t['status'] == st.session_state.dashboard_filter]

        if not filtered_tasks:
            st.info("No tasks found in this category.")
        else:
            # Professional Data Table for Drilldown
            st.dataframe(
                pd.DataFrame(filtered_tasks)[['title', 'assignee', 'company', 'status', 'priority', 'act_time']],
                use_container_width=True,
                column_config={
                    "act_time": st.column_config.NumberColumn("Hours Logged", format="%.2f h"),
                    "status": st.column_config.TextColumn("Status")
                },
                hide_index=True
            )

        st.markdown("---")

        # Row 2: Live Operations & Charts
        c_left, c_right = st.columns([2, 1])
        
        with c_left:
            st.markdown("### 🚧 Ongoing Operations (Real-Time)")
            if in_progress_count > 0:
                for t in in_progress_tasks:
                    is_running = t['timer_start'] is not None
                    status_icon = "⏳" if is_running else "⏸️"
                    border_color = "#f59e0b" if is_running else "rgba(255,255,255,0.1)"
                    
                    st.markdown(f"""
                    <div class="titan-card" style="padding: 15px; border-left: 4px solid {border_color}; margin-bottom: 10px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-weight:bold; font-size:16px;">{status_icon} {t['title']}</div>
                            <div style="font-size:12px; color:#a1a1aa;">{t['assignee']}</div>
                        </div>
                        <div style="font-size:12px; color:rgba(255,255,255,0.6); margin-top:5px;">
                            {t['company']} • {t['category']} • {t['act_time']:.2f}h logged
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No active tasks. The team is either clear or idle.")

        with c_right:
            st.markdown("### 👥 Live Attendance")
            workers = get_live_workers()
            if workers:
                for w in workers:
                    st.markdown(f"""
                    <div style="background:rgba(16, 185, 129, 0.1); border:1px solid rgba(16, 185, 129, 0.3); padding:10px; border-radius:10px; margin-bottom:8px;">
                        <div style="font-weight:bold; font-size:13px;">🟢 {w['name']}</div>
                        <div style="font-size:10px; opacity:0.7;">Online since {w['since'][11:16]}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No active shifts.")

    # --- PAGE: MY DESK ---
    elif page == "My Desk":
        st.markdown("# 💻 My Desk")
        
        my_tasks_all = [t for t in get_tasks() if t['assignee'] == user['name']]
        completed_my = [t for t in my_tasks_all if t['status'] == 'Done']
        avg_rating = 0
        rated = [t for t in completed_my if t['rating']]
        if rated: avg_rating = sum([t['rating'] for t in rated]) / len(rated)
        
        st.markdown(f"""
        <div class="titan-card" style="display:flex; justify-content:space-around; align-items:center;">
            <div style="text-align:center;">
                <div style="font-size:24px; font-weight:bold; color:#f472b6;">{avg_rating:.1f} ★</div>
                <div style="font-size:11px; text-transform:uppercase; color:#a1a1aa;">Avg Quality Rating</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:24px; font-weight:bold; color:#4ade80;">{len(completed_my)}</div>
                <div style="font-size:11px; text-transform:uppercase; color:#a1a1aa;">Tasks Finished</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("➕ Create New Task", expanded=False):
            with st.form("new_task"):
                c1, c2 = st.columns(2)
                title = c1.text_input("Task Title")
                
                users = get_all_users()
                names = users['name'].tolist()
                try: def_idx = names.index(user['name'])
                except: def_idx = 0
                assignee = c2.selectbox("Assign To", names, index=def_idx)
                
                c3, c4 = st.columns(2)
                comps = get_companies()
                if not comps: comps = ["Internal"]
                comp = c3.selectbox("Company", comps)
                cat = c4.selectbox("Category", ["Admin", "Sales", "Logistics", "IT", "Research"])
                
                if st.form_submit_button("Create Task", type="primary"):
                    add_task(title, assignee, comp, cat)
                    st.success("Task Created")
                    safe_rerun()
        
        tasks = get_tasks()
        my_tasks = [t for t in tasks if user['is_admin'] or t['assignee'] == user['name'] or True] 
        
        for t in my_tasks:
            with st.container():
                c_card, c_timer, c_edit, c_comment = st.columns([4, 2, 1, 1])
                
                with c_card:
                    timer_active = t['timer_start'] is not None
                    border_color = "#ec4899" if timer_active else ("#4ade80" if t['status']=='Done' else "rgba(255,255,255,0.1)")
                    rating_html = f"<span style='color:#fbbf24; margin-left:10px;'>{'★'*t['rating']}</span>" if t['rating'] else ""
                    
                    st.markdown(f"""
                    <div class="titan-card" style="padding: 15px; margin-bottom: 5px; border: 1px solid {border_color};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:16px; font-weight:bold;">{t['title']} {rating_html}</div>
                            <div style="font-size:11px; font-weight:bold; color:#a1a1aa; background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:4px;">{t['company']}</div>
                        </div>
                        <div style="font-size:12px; color:#a1a1aa; margin-top:5px; display:flex; gap:10px;">
                            <span>👤 {t['assignee']}</span>
                            <span>📂 {t['category']}</span>
                            <span style="color:{'#ec4899' if timer_active else 'white'}">⏱️ {t['act_time']:.2f}h Logged</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with c_timer:
                    if t['status'] != 'Done':
                        if t['timer_start']:
                            st.markdown(f"<div style='color:#ec4899; font-size:12px; text-align:center;'>Running...</div>", unsafe_allow_html=True)
                            if st.button("⏹ Stop", key=f"stop_{t['id']}", use_container_width=True):
                                toggle_task_timer(t['id'])
                                safe_rerun()
                        else:
                            st.markdown(f"<div style='height:18px;'></div>", unsafe_allow_html=True)
                            if st.button("▶ Start", key=f"start_{t['id']}", use_container_width=True):
                                toggle_task_timer(t['id'])
                                safe_rerun()
                    else:
                        if user['is_admin'] and not t['rating']:
                            with st.popover("⭐ Rate"):
                                rating = st.slider("Quality", 1, 5, 5, key=f"r_{t['id']}")
                                feed = st.text_input("Feedback", key=f"f_{t['id']}")
                                if st.button("Submit Rating", key=f"sr_{t['id']}"):
                                    rate_task(t['id'], rating, feed)
                                    st.success("Rated")
                                    safe_rerun()
                
                with c_edit:
                    st.markdown(f"<div style='height:18px;'></div>", unsafe_allow_html=True)
                    with st.popover("✏️"):
                        users = get_all_users()
                        user_list = users['name'].tolist()
                        try: curr_idx = user_list.index(t['assignee'])
                        except: curr_idx = 0
                        n_assignee = st.selectbox("Re-Assign", user_list, index=curr_idx, key=f"as_{t['id']}")
                        n_stat = st.selectbox("Status", ["To Do", "In Progress", "Done"], index=["To Do", "In Progress", "Done"].index(t['status']), key=f"s_{t['id']}")
                        n_time = st.number_input("Time (Hrs)", value=t['act_time'], key=f"t_{t['id']}")
                        if st.button("Update", key=f"up_{t['id']}"):
                            update_task(t['id'], n_stat, n_assignee, n_time)
                            safe_rerun()
                
                with c_comment:
                    st.markdown(f"<div style='height:18px;'></div>", unsafe_allow_html=True)
                    with st.popover("💬"):
                        st.markdown("**Comments**")
                        comments = get_comments(t['id'])
                        for c in comments:
                            st.markdown(f"<small><b>{c['username']}</b> ({c['timestamp']}): {c['comment']}</small>", unsafe_allow_html=True)
                            st.divider()
                        
                        new_c = st.text_input("Add comment", key=f"nc_{t['id']}")
                        if st.button("Post", key=f"pc_{t['id']}"):
                            add_comment(t['id'], user['name'], new_c)
                            safe_rerun()

    # --- PAGE: TEAM CALENDAR ---
    elif page == "Team Calendar":
        st.markdown("# 🗓️ Team Calendar")
        
        tasks = get_tasks()
        # Simple list view sorted by date for now, acting as a schedule
        sorted_tasks = sorted(tasks, key=lambda x: x['planned_date'], reverse=True)
        
        for t in sorted_tasks:
            gcal_link = create_gcal_link(f"Titan Task: {t['title']}", t['planned_date'], f"Assigned to {t['assignee']}")
            
            with st.container():
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"""
                    <div class="titan-card" style="padding: 15px; margin-bottom: 5px;">
                        <div style="font-weight:bold;">{t['title']}</div>
                        <div style="font-size:12px; opacity:0.7;">Due: {t['planned_date']} • {t['assignee']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<br>", unsafe_allow_html=True)
                    st.markdown(f'<a href="{gcal_link}" target="_blank" style="background:#4285F4; color:white; padding:8px 12px; border-radius:5px; text-decoration:none; font-size:12px; font-weight:bold;">📅 Add to GCal</a>', unsafe_allow_html=True)

    # --- PAGE: 3PL LOGISTICS ---
    elif page == "3PL Logistics":
        st.markdown("# 📦 Warehouse Control")
        
        with st.expander("➕ Create Shipment Request"):
            with st.form("ship"):
                c1, c2 = st.columns(2)
                dest = c1.selectbox("Destination", ["Amazon FBA", "Walmart WFS", "TikTok Shop"])
                inv_df = get_inventory()
                if not inv_df.empty:
                    skus_list = inv_df['sku'].tolist()
                    sel_sku = c2.selectbox("SKU", skus_list)
                else: sel_sku = c2.text_input("SKUs (Manual)")
                qty = st.number_input("Quantity", 1)
                
                if st.form_submit_button("Submit Request", type="primary"):
                    sid = f"SH-{int(time.time())}"[-6:]
                    add_shipment(f"SH-{sid}", datetime.date.today(), user['name'], dest, sel_sku, qty)
                    st.success("Created")
                    safe_rerun()
        
        ships = get_shipments()
        for s in ships:
            st.markdown(f"""
            <div class="titan-card" style="border-left: 4px solid {'#10b981' if s['status']=='Shipped' else '#3b82f6'};">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-weight:bold; font-size:16px;">{s['id']} <span style="font-weight:normal; opacity:0.7;">to {s['dest']}</span></div>
                        <div style="font-size:12px; opacity:0.6;">{s['skus']} • Requested by {s['am']}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:20px; font-weight:bold;">{s['qty']}</div>
                        <div style="font-size:10px; opacity:0.6;">UNITS</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if user['is_admin']:
                with st.expander(f"Edit {s['id']}", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    n_qty = c1.number_input("Qty", value=s['qty'], key=f"q_{s['id']}")
                    n_dest = c2.text_input("Dest", value=s['dest'], key=f"d_{s['id']}")
                    n_stat = c3.selectbox("Status", ["New", "Packing", "Shipped"], 
                                         index=["New", "Packing", "Shipped"].index(s['status']) if s['status'] in ["New", "Packing", "Shipped"] else 0,
                                         key=f"st_{s['id']}")
                    if st.button("Save Changes", key=f"sv_{s['id']}"):
                        update_shipment_details(s['id'], n_dest, s['skus'], n_qty, n_stat)
                        st.success("Updated")
                        safe_rerun()

    # --- PAGE: TEAM & REPORTS ---
    elif page == "Team & Reports":
        st.markdown("# 👥 Team & Reports")
        tab1, tab2, tab3, tab4 = st.tabs(["Manage Employees", "Manage Companies", "Work Logs", "Data Export"])
        
        with tab1:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown("### Add Employee")
                with st.form("add_user"):
                    nu = st.text_input("Username")
                    np = st.text_input("Password", type="password")
                    nn = st.text_input("Name")
                    nr = st.selectbox("Role", ["Account Manager", "Researcher", "Warehouse Labour", "CEO"])
                    if st.form_submit_button("Create"):
                        create_user(nu, np, nn, nr, False)
                        st.success("User Added")
                        safe_rerun()
            with c2: st.dataframe(get_all_users()[['name', 'role', 'username']], use_container_width=True)
        
        with tab2:
            st.markdown("### 🏢 Companies")
            c1, c2 = st.columns([1, 2])
            with c1:
                with st.form("add_comp"):
                    nc = st.text_input("Company Name")
                    if st.form_submit_button("Add Company"):
                        if add_company(nc):
                            st.success("Added")
                            safe_rerun()
                        else: st.error("Exists or Error")
            with c2: st.dataframe(pd.DataFrame(get_companies(), columns=["Company Name"]), use_container_width=True)

        with tab3:
            st.markdown("### 🕒 Employee Time Logs")
            st.dataframe(get_work_logs(), use_container_width=True)
        
        with tab4:
            st.markdown("### 💾 Export Data")
            c1, c2 = st.columns(2)
            tasks_df = pd.DataFrame(get_tasks())
            if not tasks_df.empty:
                csv = tasks_df.to_csv(index=False)
                c1.download_button("Download Tasks CSV", csv, "tasks.csv", "text/csv")
            logs_df = get_work_logs()
            if not logs_df.empty:
                csv_logs = logs_df.to_csv(index=False)
                c2.download_button("Download Work Logs CSV", csv_logs, "work_logs.csv", "text/csv")

    # --- PAGE: INVENTORY & SOPS ---
    elif page == "Inventory & SOPs":
        st.markdown("# 📚 Knowledge & Stock")
        tab1, tab2 = st.tabs(["Inventory Manager", "SOP Library"])
        
        with tab1:
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown("### Add Item")
                with st.form("add_inv"):
                    sku = st.text_input("SKU")
                    name = st.text_input("Product Name")
                    stock = st.number_input("Stock", 0)
                    loc = st.text_input("Location")
                    if st.form_submit_button("Add Stock"):
                        add_inventory(sku, name, stock, loc)
                        st.success("Added")
                        safe_rerun()
            with c2: st.dataframe(get_inventory(), use_container_width=True)
                
        with tab2:
            st.markdown("### 📖 Standard Operating Procedures")
            if user['is_admin']:
                with st.expander("➕ Add SOP"):
                    with st.form("sop"):
                        title = st.text_input("Title")
                        cat = st.selectbox("Category", ["Logistics", "Sales", "HR"])
                        content = st.text_area("Content")
                        if st.form_submit_button("Publish SOP"):
                            add_sop(title, content, cat)
                            st.success("Published")
                            safe_rerun()
            sops = get_sops()
            for index, row in sops.iterrows():
                with st.expander(f"📘 {row['title']} ({row['category']})"):
                    st.write(row['content'])

    # --- PAGE: AI ASSISTANT ---
    elif page == "AI Assistant 🤖":
        st.markdown("# 🤖 Titan AI")
        if "messages" not in st.session_state: st.session_state.messages = []
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.write(m["content"])
        if p := st.chat_input("Ask about tasks, inventory, or employees..."):
            st.session_state.messages.append({"role": "user", "content": p})
            with st.chat_message("user"): st.write(p)
            with st.chat_message("assistant"):
                if not api_key: st.error("API Key Required")
                else:
                    ctx = f"Tasks: {get_tasks()}\nLogs: {get_work_logs().to_dict()}"
                    resp = ask_gemini(p, ctx)
                    st.write(resp)
                    st.session_state.messages.append({"role": "assistant", "content": resp})
