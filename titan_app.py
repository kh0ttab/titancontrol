import streamlit as st
import pandas as pd
import datetime
import os
import time
import sqlite3
import hashlib

# --- БЕЗОПАСНЫЙ ИМПОРТ GEMINI ---
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

# --- DATABASE SETUP (PERSISTENCE) ---
DB_FILE = "titan.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT,
                    name TEXT,
                    role TEXT,
                    avatar TEXT,
                    is_admin BOOLEAN
                )''')
    
    # Tasks Table
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    assignee TEXT,
                    category TEXT,
                    priority TEXT,
                    status TEXT,
                    planned_date TEXT,
                    est_time REAL,
                    act_time REAL
                )''')
                
    # Shipments Table
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
    
    # Create Default Admin if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        # Password '123' hashed
        pwd_hash = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('admin', pwd_hash, 'Big Boss', 'CEO', '🦁', True))
        
        # Create Default Employee
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", 
                  ('alex', pwd_hash, 'Alex', 'Account Manager', '👨‍💻', False))
        
    conn.commit()
    conn.close()

# Initialize DB on load
init_db()

# --- DATABASE FUNCTIONS ---
def get_db_connection():
    return sqlite3.connect(DB_FILE)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, pwd_hash))
    user = c.fetchone()
    conn.close()
    if user:
        return {"username": user[0], "name": user[2], "role": user[3], "avatar": user[4], "is_admin": user[5]}
    return None

def get_all_users():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM users", conn)
    conn.close()
    return df

def create_user(username, password, name, role, is_admin):
    conn = get_db_connection()
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

def delete_user(username):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

def get_tasks():
    conn = get_db_connection()
    # Return as list of dicts for easier iteration
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM tasks ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_task(title, assignee, category, priority, planned_date, est_time):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title, assignee, category, priority, status, planned_date, est_time, act_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (title, assignee, category, priority, "To Do", str(planned_date), est_time, 0.0))
    conn.commit()
    conn.close()

def update_task_status(task_id, new_status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    conn.commit()
    conn.close()

def get_shipments():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM shipments ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_shipment(s_id, date, am, dest, skus, qty):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (s_id, str(date), am, dest, skus, qty, "New", ""))
    conn.commit()
    conn.close()

def update_shipment_status(s_id, new_status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE shipments SET status = ? WHERE id = ?", (new_status, s_id))
    conn.commit()
    conn.close()

# --- GEMINI AI SETUP ---
api_key = st.sidebar.text_input("🔑 Gemini API Key", type="password", placeholder="Paste Key for AI Features") if "authenticated" in st.session_state and st.session_state.authenticated else None
if api_key and AI_AVAILABLE:
    genai.configure(api_key=api_key)

def ask_gemini(prompt, context=""):
    if not AI_AVAILABLE: return "Library 'google.generativeai' not found."
    if not api_key: return "Please enter API Key."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
        response = model.generate_content(f"You are Titan AI assistant. Context: {context}. Question: {prompt}")
        return response.text
    except Exception as e: return f"Error: {e}"

# --- LIQUID GLASS THEME (CSS) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;700&display=swap');

    /* --- ANIMATED LIQUID BACKGROUND --- */
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
        color: #ffffff;
    }

    /* --- GLASS ELEMENTS --- */
    [data-testid="stSidebar"] {
        background-color: rgba(9, 9, 11, 0.6);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    h1, h2, h3, p, label, span, div {
        color: #ffffff !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    
    .titan-card {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
        margin-bottom: 15px;
    }
    .titan-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.2);
    }

    /* --- INPUTS --- */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input, .stDateInput input {
        background-color: rgba(0, 0, 0, 0.3) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
    }
    
    /* --- BUTTONS --- */
    div.stButton > button {
        background: linear-gradient(90deg, #ec4899, #8b5cf6);
        border: none;
        color: white;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(236, 72, 153, 0.3);
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5);
        transform: scale(1.02);
    }
    
    /* --- BADGES --- */
    .badge { padding: 5px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #6ee7b7 !important; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-blue { background: rgba(59, 130, 246, 0.2); color: #93c5fd !important; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #fcd34d !important; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #fca5a5 !important; border: 1px solid rgba(239, 68, 68, 0.3); }

    .login-glass {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 24px;
        padding: 40px;
        text-align: center;
        box-shadow: 0 20px 50px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def safe_rerun():
    time.sleep(0.1)
    st.rerun()

def get_efficiency_badge(task):
    if task["status"] == "Done":
        if task["act_time"] <= task["est_time"]: return '<span class="badge badge-green">Super Star</span>'
        return '<span class="badge badge-yellow">Too Slow</span>'
    try:
        planned = datetime.datetime.strptime(task["planned_date"], "%Y-%m-%d").date()
        if planned < datetime.date.today(): return '<span class="badge badge-red">Overdue</span>'
    except: pass
    return '<span class="badge badge-blue">On Track</span>'

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
        st.markdown("""
        <div class="login-glass">
            <h1 style="margin-bottom: 5px; background: linear-gradient(to right, #ec4899, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">TITAN CONTROL</h1>
            <p style="color: rgba(255,255,255,0.7); margin-bottom: 30px;">Secure Enterprise Login</p>
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("ENTER SYSTEM", type="primary", use_container_width=True)
            
            if submit:
                user = verify_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success("Access Granted.")
                    safe_rerun()
                else:
                    st.error("Invalid credentials.")
        
        st.info("Default Admin: admin / 123")

def logout_callback():
    st.session_state.authenticated = False
    st.session_state.user = None

# --- MAIN APP LOGIC ---
if not st.session_state.authenticated:
    login()
else:
    # --- LOGGED IN UI ---
    current_user = st.session_state.user
    
    # --- SIDEBAR ---
    st.sidebar.markdown("<h1>TITAN<br>CONTROL</h1>", unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
    <div class="titan-card" style="padding: 15px; margin-top: 20px; border: 1px solid rgba(255,255,255,0.2);">
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 32px;">{current_user['avatar']}</div>
            <div>
                <div style="color: white; font-weight: 700; font-size: 16px;">{current_user['name']}</div>
                <div style="color: rgba(255,255,255,0.6); font-size: 12px; text-transform: uppercase;">{current_user['role']}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")
    
    if current_user['is_admin']:
        options = ["Dashboard", "Team Management", "My Desk", "3PL Logistics", "AI Assistant 🤖"]
    else:
        options = ["My Desk", "3PL Logistics", "AI Assistant 🤖"]
        
    page = st.sidebar.radio("NAVIGATION", options)
    
    st.sidebar.markdown("---")
    st.sidebar.button("LOGOUT", on_click=logout_callback)

    # --- PAGE: DASHBOARD ---
    if page == "Dashboard":
        col_head_1, col_head_2 = st.columns([3, 1])
        with col_head_1:
            st.markdown('<h1>Executive Overview</h1>', unsafe_allow_html=True)
        
        tasks = get_tasks()
        shipments = get_shipments()
        
        total_tasks = len(tasks)
        done_tasks = len([t for t in tasks if t['status'] == 'Done'])
        velocity = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0
        pending_ships = len([s for s in shipments if s['status'] == 'New'])

        c1, c2, c3, c4 = st.columns(4)
        with c1: render_metric_card("📈", "linear-gradient(135deg, #3b82f6, #06b6d4)", f"{velocity}%", "Team Velocity", "Completion Rate")
        with c2: render_metric_card("⚡", "linear-gradient(135deg, #10b981, #34d399)", f"{total_tasks - done_tasks}", "Active Tasks", "In Pipeline")
        with c3: render_metric_card("📦", "linear-gradient(135deg, #f59e0b, #fbbf24)", f"{pending_ships}", "Warehouse Queue", "Pending Orders")
        with c4: render_metric_card("💎", "linear-gradient(135deg, #8b5cf6, #d946ef)", "85%", "Efficiency", "On Track")

        st.markdown("<br>", unsafe_allow_html=True)
        col_main_1, col_main_2 = st.columns([2, 1])
        
        with col_main_1:
            st.markdown('<h3>Recent Activity</h3>', unsafe_allow_html=True)
            for task in tasks[:5]:
                st.markdown(f"""
                <div class="titan-card" style="padding: 16px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="width: 10px; height: 10px; border-radius: 50%; background-color: {'#10b981' if task['status'] == 'Done' else '#3b82f6'}; box-shadow: 0 0 10px {'#10b981' if task['status'] == 'Done' else '#3b82f6'};"></div>
                        <div>
                            <div style="font-weight: 600; font-size: 15px;">{task['title']}</div>
                            <div style="color: rgba(255,255,255,0.5); font-size: 12px;">{task['assignee']}</div>
                        </div>
                    </div>
                    <div style="font-family: monospace; color: rgba(255,255,255,0.7); font-size: 12px;">{task['status']}</div>
                </div>
                """, unsafe_allow_html=True)

    # --- PAGE: TEAM MANAGEMENT (ADMIN ONLY) ---
    elif page == "Team Management":
        st.markdown("<h1>Team Management</h1>", unsafe_allow_html=True)
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("### Add New Employee")
            with st.form("add_user_form"):
                n_username = st.text_input("Username")
                n_password = st.text_input("Password", type="password")
                n_name = st.text_input("Full Name")
                n_role = st.selectbox("Role", ["Account Manager", "Logistics Manager", "Warehouse Lead", "Intern"])
                n_admin = st.checkbox("Grant Admin Rights")
                
                if st.form_submit_button("Create User", type="primary"):
                    if create_user(n_username, n_password, n_name, n_role, n_admin):
                        st.success(f"User {n_name} created!")
                        safe_rerun()
                    else:
                        st.error("Username already exists!")

        with c2:
            st.markdown("### Employee Directory")
            users_df = get_all_users()
            for index, user in users_df.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="titan-card" style="padding: 15px; margin-bottom: 10px; display:flex; justify-content:space-between; align-items:center;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <div style="font-size:24px;">{user['avatar']}</div>
                            <div>
                                <div style="font-weight:bold;">{user['name']}</div>
                                <div style="font-size:12px; opacity:0.7;">{user['role']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if user['username'] != 'admin': # Protect main admin
                        if st.button(f"Remove {user['username']}", key=f"del_{user['username']}"):
                            delete_user(user['username'])
                            st.success("Deleted.")
                            safe_rerun()

    # --- PAGE: MY DESK ---
    elif page == "My Desk":
        st.markdown(f"## 💻 My Desk")
        st.markdown(f"Good morning, **{current_user['name']}**.")
        
        tasks = get_tasks()
        # Filter: Show all for Admin, specific for Users
        my_tasks = [t for t in tasks if current_user['is_admin'] or current_user['name'] == t['assignee']]
        
        # --- Task Cards ---
        for task in my_tasks:
            with st.container():
                st.markdown(f"""
                <div class="titan-card" style="padding: 20px; margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <div style="font-weight: 700; font-size: 18px;">{task['title']}</div>
                        {get_efficiency_badge(task)}
                    </div>
                    <div style="font-size: 13px; color: rgba(255,255,255,0.6); display: flex; gap: 20px; margin-bottom: 15px;">
                        <span>📅 Due: {task['planned_date']}</span>
                        <span>📂 {task['category']}</span>
                        <span>👤 {task['assignee']}</span>
                        <span>⏱️ {task['act_time']} / {task['est_time']}h</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns([1, 4])
                with c1:
                    current_status = task['status']
                    new_status = st.selectbox("Status", ["To Do", "In Progress", "Done"], 
                                            index=["To Do", "In Progress", "Done"].index(current_status) if current_status in ["To Do", "In Progress", "Done"] else 0, 
                                            key=f"s_{task['id']}", label_visibility="collapsed")
                with c2:
                    if new_status != current_status:
                        update_task_status(task['id'], new_status)
                        st.toast(f"Task updated to {new_status}")
                        safe_rerun()
                st.markdown("<br>", unsafe_allow_html=True)

        # --- Add New Task Form ---
        with st.expander("+ Add New Task", expanded=True):
            with st.form("new_task"):
                c1, c2 = st.columns(2)
                t_title = c1.text_input("Title")
                
                # Get real users for dropdown
                users_df = get_all_users()
                user_names = users_df['name'].tolist()
                
                # Default to current user index if found, else 0
                try:
                    default_idx = user_names.index(current_user['name'])
                except ValueError:
                    default_idx = 0
                    
                t_assignee = c2.selectbox("Assignee", user_names, index=default_idx)
                
                c3, c4 = st.columns(2)
                t_cat = c3.selectbox("Category", ["Admin", "Sales", "Logistics", "Tech"])
                t_est = c4.number_input("Est. Hours", 1.0)
                
                if st.form_submit_button("Create Task", type="primary"):
                    add_task(t_title, t_assignee, t_cat, "Medium", datetime.date.today(), t_est)
                    st.success(f"Task Assigned to {t_assignee}!")
                    safe_rerun()

    # --- PAGE: 3PL LOGISTICS ---
    elif page == "3PL Logistics":
        st.markdown("## 📦 Warehouse Control")
        
        col_log_1, col_log_2 = st.columns([3, 1])
        with col_log_2:
            if st.button("+ New Shipment", type="primary"):
                new_id = f"SH-{int(time.time())}"[-6:] # Simple ID gen
                add_shipment(f"SH-{new_id}", datetime.date.today(), current_user['name'], "Amazon FBA", "SKU-NEW", 100)
                st.success("Draft Shipment Created")
                safe_rerun()

        shipments = get_shipments()
        for ship in shipments:
            st.markdown(f"""
            <div class="titan-card" style="margin-bottom: 15px; border-left: 4px solid {'#10b981' if ship['status']=='Shipped' else '#3b82f6'};">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <h4 style="margin:0; color: white;">{ship['id']} <span style="font-weight:400; color:rgba(255,255,255,0.6);">to {ship['dest']}</span></h4>
                        <p style="margin:5px 0 0 0; font-size: 13px; color:rgba(255,255,255,0.5);">Requested by {ship['am']} on {ship['date']}</p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 700; font-size: 18px; color: white;">{ship['qty']} <span style="font-size:12px; font-weight:400;">units</span></div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns([1, 4])
            with c1: 
                if current_user['is_admin']:
                    curr_stat = ship['status']
                    new_stat = st.selectbox("Status", ["New", "Packing", "Shipped"], 
                                          index=["New", "Packing", "Shipped"].index(curr_stat) if curr_stat in ["New", "Packing", "Shipped"] else 0, 
                                          key=f"sh_{ship['id']}", label_visibility="collapsed")
                    if new_stat != curr_stat:
                        update_shipment_status(ship['id'], new_stat)
                        safe_rerun()
                else:
                    st.info(ship['status'])
            st.markdown("---")

    # --- PAGE: AI ASSISTANT ---
    elif page == "AI Assistant 🤖":
        st.markdown("## 🤖 Titan AI Chat")
        
        if "messages" not in st.session_state: st.session_state.messages = []
        
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.write(msg["content"])

        if prompt := st.chat_input("Ask Titan AI..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.write(prompt)
            
            with st.chat_message("assistant"):
                if not api_key: st.error("Please enter API Key in sidebar")
                else:
                    with st.spinner("Thinking..."):
                        tasks = get_tasks()
                        shipments = get_shipments()
                        context = f"Tasks: {tasks}\nShipments: {shipments}"
                        resp = ask_gemini(prompt, context)
                        st.write(resp)
                        st.session_state.messages.append({"role": "assistant", "content": resp})
