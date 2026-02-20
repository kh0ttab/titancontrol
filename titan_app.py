import streamlit as st
import pandas as pd
import datetime
import os
import time
import sqlite3
import hashlib
import re
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
    
    # 1. Users (Added email column)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    name TEXT,
                    role TEXT,
                    avatar TEXT,
                    is_admin BOOLEAN,
                    email TEXT
                )''')
    
    # DB Migration checks (Graceful updates for existing DBs)
    try: c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except: pass
    
    try: c.execute("ALTER TABLE tasks ADD COLUMN company TEXT")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN timer_start TEXT")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN rating INTEGER")
    except: pass
    try: c.execute("ALTER TABLE tasks ADD COLUMN feedback TEXT")
    except: pass
                
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

    # 8. Task Comments
    c.execute('''CREATE TABLE IF NOT EXISTS task_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    username TEXT,
                    comment TEXT,
                    timestamp TEXT
                )''')
    
    # Seed Default Data (with default emails)
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, name, role, avatar, is_admin, email) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('admin', pwd_hash, 'Big Boss', 'CEO', '🦁', True, 'admin@titan.com'))
    
    c.execute("SELECT * FROM users WHERE username = 'alex'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, name, role, avatar, is_admin, email) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('alex', pwd_hash, 'Alex', 'Account Manager', '👨‍💻', False, 'alex@titan.com'))

    c.execute("SELECT * FROM users WHERE username = 'sarah'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, name, role, avatar, is_admin, email) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('sarah', pwd_hash, 'Sarah', 'Researcher', '🔎', False, 'sarah@titan.com'))

    c.execute("SELECT * FROM users WHERE username = 'mike'")
    if not c.fetchone():
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, name, role, avatar, is_admin, email) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('mike', pwd_hash, 'Mike', 'Warehouse Labour', '📦', False, 'mike@titan.com'))
    
    # Backfill missing emails for older DB versions
    c.execute("UPDATE users SET email = username || '@titan.com' WHERE email IS NULL")
    
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

def verify_user(identifier, password):
    """Verifies a user by either Username OR Email."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    pwd_hash = hash_password(password)
    
    try:
        c.execute("SELECT * FROM users WHERE (username=? OR email=?) AND password=?", (identifier, identifier, pwd_hash))
    except sqlite3.OperationalError:
        # Fallback if email column doesn't exist for some reason
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (identifier, pwd_hash))
        
    user = c.fetchone()
    conn.close()
    
    if user:
        return dict(user)
    return None

def create_user(username, password, name, role, is_admin, email):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, name, role, avatar, is_admin, email) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  (username, hash_password(password), name, role, '👤', is_admin, email))
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

def get_task_by_id(task_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

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

def handle_task_timer(task_id, action):
    """Handles Start, Pause, and Stop explicitly without toggle ambiguity"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT timer_start, act_time FROM tasks WHERE id=?", (task_id,))
    row = c.fetchone()
    
    if row:
        start_ts, current_act = row
        current_act = current_act if current_act else 0.0
        
        if start_ts and action in ['pause', 'stop']:
            start_dt = datetime.datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
            diff_hours = (datetime.datetime.now() - start_dt).total_seconds() / 3600.0
            new_act = current_act + diff_hours
            
            if action == 'pause':
                c.execute("UPDATE tasks SET timer_start=NULL, act_time=? WHERE id=?", (new_act, task_id))
                st.toast(f"Timer Paused. Added {diff_hours:.2f} hours.")
            elif action == 'stop':
                c.execute("UPDATE tasks SET timer_start=NULL, act_time=?, status='Done' WHERE id=?", (new_act, task_id))
                st.toast(f"Task Completed! Added {diff_hours:.2f} hours.")
                
        elif not start_ts and action == 'start':
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

# --- CSS STYLING (FLUID GLASS SPACE GRADIENT & ULTRA-MODERN SIDEBAR) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

    /* --- BACKGROUND & GLOBAL --- */
    .stApp {
        background-color: #271759;
        background-image: linear-gradient(120deg, #271759 0%, #0a719c 45%, #11c99f 100%);
        background-attachment: fixed;
        background-size: cover;
        font-family: 'Outfit', sans-serif;
        color: white;
    }

    /* --- SIDEBAR GLASS (SEAMLESS & FLUID) --- */
    [data-testid="stSidebar"] {
        background: rgba(13, 17, 30, 0.55) !important; 
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    
    /* --- SIDEBAR TITLES & TEXT --- */
    [data-testid="stSidebar"] .titan-title {
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 8px;
        margin-top: 15px;
        padding-left: 14px; 
    }

    /* --- NAVIGATION MENU TILES (FLUID LEFT-ALIGNED UI) --- */
    [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child { display: none; }
    [data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] { 
        gap: 2px; 
        padding: 0 10px; 
    }

    /* Unselected Tile */
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background: transparent !important; 
        border: none !important; 
        border-radius: 8px !important;
        padding: 12px 14px !important;
        margin-bottom: 2px !important;
        transition: all 0.3s ease !important;
        display: flex;
        align-items: center;
        justify-content: flex-start !important; 
        width: 100% !important;
        box-shadow: none !important;
        cursor: pointer;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(255, 255, 255, 0.04) !important; 
        transform: translateX(4px); 
    }

    /* Selected Tile */
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
        background: linear-gradient(90deg, rgba(255, 255, 255, 0.1) 0%, rgba(255, 255, 255, 0.01) 100%) !important; 
        box-shadow: inset 3px 0 0 0 #17D29F !important; 
        border-radius: 4px 8px 8px 4px !important;
        transform: translateX(4px);
    }

    /* Tile Typography */
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {
        color: #94a3b8 !important; 
        font-weight: 500 !important; 
        font-size: 14.5px !important; 
        margin: 0 !important;
        transition: color 0.3s ease;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover p {
        color: #cbd5e1 !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {
        color: #ffffff !important; 
        font-weight: 600 !important;
        letter-spacing: 0.3px;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.2);
    }
    
    /* --- SIDEBAR BUTTONS (Like CLOCK IN) --- */
    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, rgba(61,97,255,0.9), rgba(23,210,159,0.9)) !important;
        border-radius: 8px !important; 
        padding: 8px 20px !important;
        width: calc(100% - 20px) !important; 
        margin: 5px 10px 15px 10px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(23, 210, 159, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    [data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(23, 210, 159, 0.4) !important;
        opacity: 1 !important;
    }

    /* Pulse Animation for Online Dot */
    @keyframes pulse-dot {
        0% { box-shadow: 0 0 0 0 rgba(23, 210, 159, 0.5); }
        70% { box-shadow: 0 0 0 6px rgba(23, 210, 159, 0); }
        100% { box-shadow: 0 0 0 0 rgba(23, 210, 159, 0); }
    }

    /* --- SECONDARY BUTTONS (Solid & Neat UI - NO GLASS) --- */
    div.stButton > button[kind="secondary"] {
        background: #1e293b; /* Solid elegant slate blue */
        border: 1px solid #334155;
        color: #f8fafc;
        border-radius: 6px; /* Neat corners */
        transition: all 0.2s ease;
        padding: 6px 14px;
        white-space: pre-wrap;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div.stButton > button[kind="secondary"]:hover {
        background: #334155; /* Slightly lighter solid */
        border-color: #475569;
        transform: translateY(-1px);
        color: white;
    }
    
    /* --- PRIMARY BUTTONS (Main Action UI - NO GLASS) --- */
    .main div.stButton > button[kind="primary"] {
        background: #ef4444; /* Vivid neat red for standard stop/create actions */
        border: 1px solid #dc2626;
        color: white;
        border-radius: 6px; 
        font-weight: 600;
        letter-spacing: 0.2px;
        transition: all 0.2s ease;
        box-shadow: 0 2px 6px rgba(239, 68, 68, 0.3);
    }
    .main div.stButton > button[kind="primary"]:hover {
        background: #dc2626; 
        border-color: #b91c1c;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(239, 68, 68, 0.4);
    }

    /* --- TITAN ELEMENTS --- */
    h1, h2, h3 {
        color: white !important;
        text-shadow: 0px 2px 10px rgba(0,0,0,0.3);
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .titan-card {
        background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(16px);
        border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 24px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1); margin-bottom: 15px;
    }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input {
        background-color: rgba(15, 23, 42, 0.6) !important; color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important; border-radius: 8px !important;
    }
    /* Style Tabs to look modern */
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; gap: 20px; }
    .stTabs [data-baseweb="tab"] { color: #e2e8f0; background-color: transparent; border-radius: 8px 8px 0 0; }
    .stTabs [aria-selected="true"] { color: #17D29F !important; border-bottom-color: #17D29F !important; }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def safe_rerun():
    time.sleep(0.1)
    st.rerun()

# --- AUTHENTICATION FLOW ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.15); border-radius: 24px; padding: 40px; text-align: center; margin-bottom: 25px;">
            <h1 style="font-size: 42px; margin-bottom: 5px;">TITAN CONTROL</h1>
            <p style="color: #e2e8f0; font-size: 18px;">Secure Enterprise Access</p>
        </div>
        """, unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["🔒 Secure Login", "📝 Create Account"])
        
        with tab_login:
            with st.form("login_form"):
                u = st.text_input("Email Address or Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("LOGIN", type="primary", use_container_width=True):
                    user = verify_user(u, p)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success("Authenticated Successfully")
                        safe_rerun()
                    else:
                        st.error("Access Denied. Check credentials.")
            st.info("Demo Account: admin@titan.com / 123")
            
        with tab_register:
            with st.form("register_form"):
                new_email = st.text_input("Real Email Address *")
                new_username = st.text_input("Desired Username *")
                new_name = st.text_input("Full Name *")
                new_role = st.selectbox("Role", ["Employee", "Account Manager", "Researcher", "Admin"])
                new_pass = st.text_input("Password *", type="password")
                new_pass2 = st.text_input("Confirm Password *", type="password")
                
                if st.form_submit_button("REGISTER NOW", type="primary", use_container_width=True):
                    # --- REAL EMAIL VALIDATION ---
                    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
                    
                    if not re.match(email_regex, new_email):
                        st.error("⚠️ Please enter a valid, real email address.")
                    elif not new_username or not new_name or not new_pass:
                        st.error("⚠️ Please fill in all required fields.")
                    elif new_pass != new_pass2:
                        st.error("⚠️ Passwords do not match.")
                    elif len(new_pass) < 6:
                        st.error("⚠️ Password must be at least 6 characters.")
                    else:
                        success = create_user(
                            username=new_username, 
                            password=new_pass, 
                            name=new_name, 
                            role=new_role, 
                            is_admin=(new_role=="Admin"),
                            email=new_email
                        )
                        if success:
                            st.success("✅ Account created! You can now log in using the Login tab.")
                        else:
                            st.error("⚠️ Username or Email is already registered.")

if not st.session_state.authenticated:
    login()
else:
    user = st.session_state.user
    
    # --- SIDEBAR UI (SEAMLESS & CLEAN) ---
    st.sidebar.markdown('<div class="titan-title" style="margin-top: 5px;">TITAN OS</div>', unsafe_allow_html=True)
    
    # Big Boss Style User Card (No more clunky box, blends into sidebar)
    st.sidebar.markdown(f"""
    <div style="padding: 5px 14px 20px 14px; border-bottom: 1px solid rgba(255,255,255,0.05); display: flex; align-items: center; gap: 14px;">
        <div style="font-size: 20px; background: linear-gradient(135deg, rgba(255,255,255,0.15), rgba(255,255,255,0.02)); width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid rgba(255,255,255,0.1); box-shadow: inset 0 2px 4px rgba(255,255,255,0.05);">{user['avatar']}</div>
        <div style="line-height: 1.2;">
            <div style="font-weight: 700; font-size: 15.5px; color: white; letter-spacing: 0.2px;">{user['name']}</div>
            <div style="font-size: 11.5px; color: #94a3b8; font-weight: 500;">{user['role']}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown('<div class="titan-title">TIME CLOCK</div>', unsafe_allow_html=True)
    last_event = get_last_work_event(user['username'])
    is_working = last_event and last_event[0] == 'CLOCK_IN'
    
    if is_working:
        # Seamless Online Indicator with CSS Pulse
        st.sidebar.markdown(f"""
        <div style="margin: 0 10px 10px 10px; padding: 10px 12px; display: flex; align-items: center; color: #17D29F; font-size: 13.5px; font-weight: 500; background: rgba(23, 210, 159, 0.05); border-radius: 8px;">
            <div style="width: 8px; height: 8px; background: #17D29F; border-radius: 50%; display: inline-block; margin-right: 12px; animation: pulse-dot 2s infinite;"></div>
            Working since {last_event[1][11:16]}
        </div>
        """, unsafe_allow_html=True)
        if st.sidebar.button("CLOCK OUT", type="primary"):
            log_work_event(user['username'], 'CLOCK_OUT')
            st.success("Shift Ended")
            safe_rerun()
    else:
        # Seamless Offline Indicator
        st.sidebar.markdown(f"""
        <div style="margin: 0 10px 10px 10px; padding: 10px 12px; display: flex; align-items: center; color: #94a3b8; font-size: 13.5px; font-weight: 500; background: rgba(255,255,255,0.02); border-radius: 8px;">
            <div style="width: 8px; height: 8px; background: #475569; border-radius: 50%; display: inline-block; margin-right: 12px;"></div>
            Currently Offline
        </div>
        """, unsafe_allow_html=True)
        if st.sidebar.button("CLOCK IN", type="primary"):
            log_work_event(user['username'], 'CLOCK_IN')
            st.success("Shift Started")
            safe_rerun()

    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    # Fluid Left-Aligned Navigation List
    nav_opts = ["Dashboard", "My Desk", "Team Calendar", "3PL Logistics", "Team & Reports", "Inventory & SOPs", "AI Assistant 🤖"]
    page = st.sidebar.radio("Navigation", nav_opts, label_visibility="hidden")
    
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    if st.sidebar.button("LOGOUT", type="primary"):
        st.session_state.authenticated = False
        safe_rerun()

    # --- PAGE: DASHBOARD ---
    if page == "Dashboard":
        # Handle Master-Detail State
        if "view_task_id" not in st.session_state:
            st.session_state.view_task_id = None

        # -- DETAIL VIEW --
        if st.session_state.view_task_id:
            t = get_task_by_id(st.session_state.view_task_id)
            if t:
                if st.button("⬅ Back to Dashboard", key="back_btn", type="secondary"):
                    st.session_state.view_task_id = None
                    safe_rerun()
                    
                st.markdown(f"# 📌 {t['title']}")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"""
                    <div class="titan-card">
                        <h3 style="margin-top:0">Task Details</h3>
                        <p><b>Assignee:</b> {t['assignee']}</p>
                        <p><b>Company:</b> {t['company']}</p>
                        <p><b>Category:</b> {t['category']}</p>
                        <p><b>Status:</b> {t['status']}</p>
                        <p><b>Total Time:</b> {t['act_time']:.2f} hrs</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Timer Controls in Detail View
                    if t['status'] != 'Done':
                        if t['timer_start']:
                            st.info("Timer is RUNNING")
                            tc1, tc2 = st.columns(2)
                            if tc1.button("⏸ Pause Timer", key="det_pause", type="secondary", use_container_width=True):
                                handle_task_timer(t['id'], 'pause')
                                safe_rerun()
                            if tc2.button("⏹ Stop & Finish", key="det_stop", type="primary", use_container_width=True):
                                handle_task_timer(t['id'], 'stop')
                                safe_rerun()
                        else:
                            if st.button("▶ Start Timer", key="det_start", type="secondary", use_container_width=True):
                                handle_task_timer(t['id'], 'start')
                                safe_rerun()

                with c2:
                    st.markdown("### 💬 Comments")
                    comments = get_comments(t['id'])
                    with st.container(height=300):
                        for c in comments:
                            st.markdown(f"**{c['username']}**: {c['comment']}")
                            st.caption(f"{c['timestamp']}")
                            st.divider()
                    
                    new_c = st.text_input("Add a note...")
                    if st.button("Post Comment", type="primary"):
                        add_comment(t['id'], user['name'], new_c)
                        safe_rerun()

        # -- DASHBOARD VIEW --
        else:
            st.markdown("# Executive Overview")
            
            tasks = get_tasks()
            total = len(tasks)
            in_progress = len([t for t in tasks if t['status'] == 'In Progress'])
            todo = len([t for t in tasks if t['status'] == 'To Do'])
            done = len([t for t in tasks if t['status'] == 'Done'])
            completion = int((done/total*100)) if total > 0 else 0

            # Session Filter
            if "dash_filter" not in st.session_state: st.session_state.dash_filter = "In Progress"

            # Clickable Tiles using styled buttons
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button(f"⚡\n{total}\nTOTAL TASKS", type="secondary", use_container_width=True):
                    st.session_state.dash_filter = "All"
                    safe_rerun()
            with c2:
                if st.button(f"🔥\n{in_progress}\nIN PROGRESS", type="secondary", use_container_width=True):
                    st.session_state.dash_filter = "In Progress"
                    safe_rerun()
            with c3:
                if st.button(f"📋\n{todo}\nTO DO", type="secondary", use_container_width=True):
                    st.session_state.dash_filter = "To Do"
                    safe_rerun()
            with c4:
                if st.button(f"✅\n{completion}%\nCOMPLETION", type="secondary", use_container_width=True):
                    st.session_state.dash_filter = "Done"
                    safe_rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"### 🔎 {st.session_state.dash_filter} Tasks")
            
            # Filters
            fc1, fc2, fc3 = st.columns([2, 1, 1])
            search = fc1.text_input("Search", placeholder="Search tasks...", label_visibility="collapsed")
            
            all_companies = sorted(list(set([t['company'] for t in tasks if t['company']])))
            all_priorities = ["High", "Medium", "Low"]
            
            filter_company = fc2.multiselect("Company", all_companies, placeholder="Company", label_visibility="collapsed")
            filter_priority = fc3.multiselect("Priority", all_priorities, placeholder="Priority", label_visibility="collapsed")

            # Filter Logic
            filtered = tasks
            if st.session_state.dash_filter != "All":
                filtered = [t for t in tasks if t['status'] == st.session_state.dash_filter]
            
            if search:
                filtered = [t for t in filtered if search.lower() in t['title'].lower() or search.lower() in t['assignee'].lower()]
            if filter_company:
                filtered = [t for t in filtered if t['company'] in filter_company]
            if filter_priority:
                filtered = [t for t in filtered if t['priority'] in filter_priority]

            # Modern Data Grid with Selection
            df = pd.DataFrame(filtered)
            if not df.empty:
                event = st.dataframe(
                    df[['title', 'assignee', 'company', 'status', 'priority', 'act_time']],
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "act_time": st.column_config.NumberColumn("Hours", format="%.2f"),
                        "status": st.column_config.TextColumn("Status"),
                        "priority": st.column_config.Column("Priority", width="small"),
                        "company": st.column_config.Column("Company", width="medium"),
                        "title": st.column_config.Column("Task", width="large")
                    },
                    hide_index=True
                )
                
                # Handling Selection to Open Detail View
                if len(event.selection.rows) > 0:
                    selected_index = event.selection.rows[0]
                    # Find correct ID
                    task_id = df.iloc[selected_index]['id'] if 'id' in df.columns else filtered[selected_index]['id']
                    st.session_state.view_task_id = int(task_id)
                    safe_rerun()
            else:
                st.info("No tasks found.")

            # Live Attendance Section
            st.markdown("---")
            st.markdown("### 👥 Live Attendance")
            workers = get_live_workers()
            if workers:
                cols = st.columns(4)
                for i, w in enumerate(workers):
                    with cols[i % 4]:
                        st.markdown(f"""
                        <div style="background:rgba(23, 210, 159, 0.15); border:1px solid #17D29F; padding:10px; border-radius:10px;">
                            <div style="font-weight:bold; color:white;">{w['name']}</div>
                            <div style="font-size:12px; color:#17D29F;">Online since {w['since'][11:16]}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.caption("No active shifts.")

    # --- OTHER PAGES ---
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
                <div style="font-size:24px; font-weight:bold; color:#FF4081;">{avg_rating:.1f} ★</div>
                <div style="font-size:11px; text-transform:uppercase; color:#e2e8f0;">Avg Quality Rating</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:24px; font-weight:bold; color:#17D29F;">{len(completed_my)}</div>
                <div style="font-size:11px; text-transform:uppercase; color:#e2e8f0;">Tasks Finished</div>
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
                    border_color = "#3D61FF" if timer_active else ("#17D29F" if t['status']=='Done' else "rgba(255,255,255,0.08)")
                    rating_html = f"<span style='color:#fbbf24; margin-left:10px;'>{'★'*t['rating']}</span>" if t['rating'] else ""
                    
                    st.markdown(f"""
                    <div class="titan-card" style="padding: 15px; margin-bottom: 5px; border: 1px solid {border_color};">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:16px; font-weight:bold; color:white;">{t['title']} {rating_html}</div>
                            <div style="font-size:11px; font-weight:bold; color:#e2e8f0; background:rgba(255,255,255,0.15); padding:2px 8px; border-radius:4px;">{t['company']}</div>
                        </div>
                        <div style="font-size:12px; color:#cbd5e1; margin-top:5px; display:flex; gap:10px;">
                            <span>👤 {t['assignee']}</span>
                            <span>📂 {t['category']}</span>
                            <span style="color:{'#17D29F' if timer_active else 'white'}">⏱️ {t['act_time']:.2f}h Logged</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with c_timer:
                    if t['status'] != 'Done':
                        if t['timer_start']:
                            st.markdown(f"<div style='color:#17D29F; font-size:12px; text-align:center; padding-bottom: 5px;'>Running...</div>", unsafe_allow_html=True)
                            tc1, tc2 = st.columns(2)
                            if tc1.button("⏸ Pause", key=f"pause_{t['id']}", help="Pause without finishing", type="secondary", use_container_width=True):
                                handle_task_timer(t['id'], 'pause')
                                safe_rerun()
                            if tc2.button("⏹ Stop", key=f"stop_{t['id']}", help="Stop and Mark Done", type="primary", use_container_width=True):
                                handle_task_timer(t['id'], 'stop')
                                safe_rerun()
                        else:
                            st.markdown(f"<div style='height:24px;'></div>", unsafe_allow_html=True)
                            if st.button("▶ Start", key=f"start_{t['id']}", type="secondary", use_container_width=True):
                                handle_task_timer(t['id'], 'start')
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
                    st.markdown(f"<div style='height:24px;'></div>", unsafe_allow_html=True)
                    with st.popover("✏️"):
                        users = get_all_users()
                        user_list = users['name'].tolist()
                        try: curr_idx = user_list.index(t['assignee'])
                        except: curr_idx = 0
                        n_assignee = st.selectbox("Re-Assign", user_list, index=curr_idx, key=f"as_{t['id']}")
                        n_stat = st.selectbox("Status", ["To Do", "In Progress", "Done"], index=["To Do", "In Progress", "Done"].index(t['status']), key=f"s_{t['id']}")
                        n_time = st.number_input("Time (Hrs)", value=t['act_time'], key=f"t_{t['id']}")
                        if st.button("Update", key=f"up_{t['id']}", type="primary"):
                            update_task(t['id'], n_stat, n_assignee, n_time)
                            safe_rerun()
                
                with c_comment:
                    st.markdown(f"<div style='height:24px;'></div>", unsafe_allow_html=True)
                    with st.popover("💬"):
                        st.markdown("**Comments**")
                        comments = get_comments(t['id'])
                        for c in comments:
                            st.markdown(f"<small><b>{c['username']}</b> ({c['timestamp']}): {c['comment']}</small>", unsafe_allow_html=True)
                            st.divider()
                        
                        new_c = st.text_input("Add comment", key=f"nc_{t['id']}")
                        if st.button("Post", key=f"pc_{t['id']}", type="secondary"):
                            add_comment(t['id'], user['name'], new_c)
                            safe_rerun()

    elif page == "3PL Logistics":
        st.markdown("# 📦 Warehouse Control")
        with st.expander("➕ Create Shipment"):
            with st.form("ship"):
                c1, c2 = st.columns(2)
                dest = c1.selectbox("Dest", ["Amazon", "Walmart"])
                sku = c2.text_input("SKU")
                qty = st.number_input("Qty", 1)
                if st.form_submit_button("Submit", type="primary"):
                    add_shipment(f"SH-{int(time.time())}", datetime.date.today(), user['name'], dest, sku, qty)
                    st.success("Created")
                    safe_rerun()
        for s in get_shipments():
            st.markdown(f"<div class='titan-card'>{s['id']} to {s['dest']} ({s['qty']} units)</div>", unsafe_allow_html=True)

    elif page == "Team & Reports":
        st.markdown("# 👥 Team & Reports")
        st.dataframe(get_all_users(), use_container_width=True)

    elif page == "Inventory & SOPs":
        st.markdown("# 📚 Inventory")
        st.dataframe(get_inventory(), use_container_width=True)

    elif page == "Team Calendar":
        st.markdown("# 📅 Calendar")
        st.info("Calendar module is active. Create tasks to see them scheduled here.")

    elif page == "AI Assistant 🤖":
        st.markdown("# 🤖 AI Chat")
        if p := st.chat_input("Ask Titan AI..."):
            st.write("AI Processing...")
