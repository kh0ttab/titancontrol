import streamlit as st
import pandas as pd
import datetime
import os
import time

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

    /* --- SIDEBAR GLASS --- */
    [data-testid="stSidebar"] {
        background-color: rgba(9, 9, 11, 0.6);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Typography Overrides */
    h1, h2, h3, p, label, span, div {
        color: #ffffff !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    [data-testid="stSidebar"] h1 {
        background: linear-gradient(to right, #c084fc, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent !important;
        text-shadow: none;
        font-weight: 800;
        letter-spacing: -1px;
    }

    /* --- GLASS CARDS --- */
    .titan-card {
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
        margin-bottom: 15px;
    }
    .titan-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.4);
        border-color: rgba(255, 255, 255, 0.2);
    }

    /* --- METRICS GLOW --- */
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        background: linear-gradient(135deg, #ffffff 0%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    .metric-label {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.7) !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .metric-sub {
        font-size: 12px;
        color: rgba(255, 255, 255, 0.5) !important;
    }

    /* --- INPUT FIELDS & SELECTBOXES --- */
    /* Force dark background on inputs for readability */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stNumberInput input, .stDateInput input {
        background-color: rgba(0, 0, 0, 0.3) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
    }
    .stSelectbox div[data-baseweb="select"] span {
        color: white !important;
    }
    /* Dropdown menu items */
    ul[data-baseweb="menu"] {
        background-color: #18181b !important;
    }
    
    /* --- DATAFRAME --- */
    div[data-testid="stDataFrame"] {
        background-color: rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 10px;
    }
    /* Darken dataframe text for contrast if needed, or keep white */
    div[data-testid="stDataFrame"] div {
        color: #e4e4e7;
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
    div.stButton > button:active {
        transform: scale(0.98);
    }
    
    /* --- BADGES & ICONS --- */
    .icon-box {
        width: 48px;
        height: 48px;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        margin-bottom: 15px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.1);
        backdrop-filter: blur(5px);
    }
    
    .badge {
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #6ee7b7 !important; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-blue { background: rgba(59, 130, 246, 0.2); color: #93c5fd !important; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #fcd34d !important; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #fca5a5 !important; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-purple { background: rgba(139, 92, 246, 0.2); color: #c4b5fd !important; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* Login Box Specifics */
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

# --- SAFE RERUN FUNCTION ---
def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        try:
            st.experimental_rerun()
        except AttributeError:
            pass

# --- DATA INITIALIZATION ---
EMPLOYEES = [
    {"id": "ceo", "username": "admin", "password": "123", "name": "Big Boss", "role": "CEO", "avatar": "🦁", "is_admin": True},
    {"id": "alex", "username": "alex", "password": "123", "name": "Alex", "role": "Account Manager", "avatar": "👨‍💻", "is_admin": False},
    {"id": "sarah", "username": "sarah", "password": "123", "name": "Sarah", "role": "Logistics Manager", "avatar": "👩‍✈️", "is_admin": True},
    {"id": "mike", "username": "mike", "password": "123", "name": "Mike", "role": "Warehouse Lead", "avatar": "👷", "is_admin": True},
]

if "tasks" not in st.session_state:
    st.session_state.tasks = [
        {"id": 1, "title": "Q4 Strategy Report", "assignee": "Big Boss", "category": "Admin", "priority": "High", "status": "In Progress", "planned_date": "2023-11-15", "est_time": 4.0, "act_time": 2.0},
        {"id": 2, "title": "Update Amazon Listings", "assignee": "Alex", "category": "Sales", "priority": "Medium", "status": "Done", "planned_date": "2023-11-10", "est_time": 2.0, "act_time": 1.5},
        {"id": 3, "title": "Fix Walmart CSV Error", "assignee": "Alex", "category": "Tech", "priority": "High", "status": "To Do", "planned_date": "2023-11-12", "est_time": 1.0, "act_time": 0.0},
        {"id": 4, "title": "Prepare FBA Shipment #442", "assignee": "Sarah", "category": "Logistics", "priority": "High", "status": "In Progress", "planned_date": "2023-11-14", "est_time": 3.0, "act_time": 4.0},
        {"id": 5, "title": "Warehouse Inventory Audit", "assignee": "Mike", "category": "Logistics", "priority": "Medium", "status": "Done", "planned_date": "2023-11-01", "est_time": 5.0, "act_time": 5.0},
        {"id": 6, "title": "TikTok Shop Integration", "assignee": "Alex", "category": "Sales", "priority": "Low", "status": "To Do", "planned_date": "2023-11-20", "est_time": 8.0, "act_time": 0.0},
    ]

if "shipments" not in st.session_state:
    st.session_state.shipments = [
        {"id": "SH-001", "date": "2023-11-12", "am": "Alex", "dest": "Amazon FBA", "skus": "SKU-A, SKU-B", "qty": 500, "status": "Shipped", "tracking": "1Z999222"},
        {"id": "SH-002", "date": "2023-11-13", "am": "Alex", "dest": "Walmart WFS", "skus": "SKU-C", "qty": 120, "status": "Packing", "tracking": ""},
        {"id": "SH-003", "date": "2023-11-14", "am": "Sarah", "dest": "TikTok Shop", "skus": "SKU-A", "qty": 50, "status": "New", "tracking": ""},
    ]

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

# --- HELPER FUNCTIONS ---
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
        <div class="icon-box" style="background: {gradient}; color: white;">
            {icon}
        </div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-sub">{sub}</div>
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
            <p style="color: rgba(255,255,255,0.7); margin-bottom: 30px;">Future Enterprise OS</p>
        </div>
        <br>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("ENTER SYSTEM", type="primary", use_container_width=True)
            
            if submit:
                user = next((u for u in EMPLOYEES if u["username"] == username and u["password"] == password), None)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.success("Access Granted.")
                    time.sleep(0.5)
                    safe_rerun()
                else:
                    st.error("Access Denied.")
        
        st.info("Demo Access: admin / 123 (CEO) OR alex / 123 (Employee)")

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
        options = ["Dashboard", "Master Registry", "My Desk", "3PL Logistics", "AI Assistant 🤖"]
    else:
        options = ["My Desk", "3PL Logistics", "AI Assistant 🤖"]
        
    page = st.sidebar.radio("NAVIGATION", options)
    
    st.sidebar.markdown("---")
    st.sidebar.button("LOGOUT", on_click=logout_callback)

    # --- PAGES ---

    # 1. ADMIN DASHBOARD
    if page == "Dashboard":
        col_head_1, col_head_2 = st.columns([3, 1])
        with col_head_1:
            st.markdown('<h1>Executive Overview</h1>', unsafe_allow_html=True)
            st.markdown('<p style="color: rgba(255,255,255,0.7);">Live operational metrics.</p>', unsafe_allow_html=True)
        
        # Logic
        df_tasks = pd.DataFrame(st.session_state.tasks)
        total_tasks = len(df_tasks)
        done_tasks = len(df_tasks[df_tasks['status'] == 'Done'])
        velocity = int((done_tasks / total_tasks) * 100) if total_tasks > 0 else 0
        pending_ships = len([s for s in st.session_state.shipments if s['status'] == 'New'])

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_metric_card("📈", "linear-gradient(135deg, #3b82f6, #06b6d4)", f"{velocity}%", "Team Velocity", "+12% vs last week")
        with c2: render_metric_card("⚡", "linear-gradient(135deg, #10b981, #34d399)", f"{total_tasks - done_tasks}", "Active Tasks", "In pipeline")
        with c3: render_metric_card("📦", "linear-gradient(135deg, #f59e0b, #fbbf24)", f"{pending_ships}", "Warehouse Queue", "Pending Orders")
        with c4: render_metric_card("💎", "linear-gradient(135deg, #8b5cf6, #d946ef)", "85%", "Efficiency", "On Track")

        st.markdown("<br>", unsafe_allow_html=True)

        col_main_1, col_main_2 = st.columns([2, 1])
        with col_main_1:
            st.markdown('<h3>Recent Activity</h3>', unsafe_allow_html=True)
            for task in st.session_state.tasks[:4]:
                st.markdown(f"""
                <div class="titan-card" style="padding: 16px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="width: 10px; height: 10px; border-radius: 50%; background-color: {'#10b981' if task['status'] == 'Done' else '#3b82f6'}; box-shadow: 0 0 10px {'#10b981' if task['status'] == 'Done' else '#3b82f6'};"></div>
                        <div>
                            <div style="font-weight: 600; font-size: 15px;">{task['title']}</div>
                            <div style="color: rgba(255,255,255,0.5); font-size: 12px;">{task['assignee']}</div>
                        </div>
                    </div>
                    <div style="font-family: monospace; color: rgba(255,255,255,0.7); font-size: 12px;">{task['act_time']}h logged</div>
                </div>
                """, unsafe_allow_html=True)

        with col_main_2:
            st.markdown('<h3>3PL Status</h3>', unsafe_allow_html=True)
            for ship in st.session_state.shipments[:3]:
                badge_cls = "badge-green" if ship['status'] == "Shipped" else "badge-purple" if ship['status'] == "New" else "badge-blue"
                st.markdown(f"""
                <div class="titan-card" style="padding: 16px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 5px;">
                        <div style="font-weight: 600; font-size: 14px;">{ship['dest']}</div>
                        <span class="badge {badge_cls}">{ship['status']}</span>
                    </div>
                    <div style="font-size: 12px; color: rgba(255,255,255,0.6);">{ship['id']} • {ship['qty']} units</div>
                </div>
                """, unsafe_allow_html=True)

    # 2. MY DESK
    elif page == "My Desk":
        st.markdown(f"## 💻 My Desk")
        st.markdown(f"Good morning, **{current_user['name']}**.")
        
        my_tasks = [t for t in st.session_state.tasks if current_user['is_admin'] or current_user['name'] in t['assignee']]
        
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
                    new_status = st.selectbox("Status", ["To Do", "In Progress", "Done"], index=["To Do", "In Progress", "Done"].index(task['status']) if task['status'] in ["To Do", "In Progress", "Done"] else 0, key=f"s_{task['id']}", label_visibility="collapsed")
                with c2:
                    if new_status != task['status']:
                        task['status'] = new_status
                        safe_rerun()
                st.markdown("<br>", unsafe_allow_html=True)

        with st.expander("+ Add New Task", expanded=True):
            with st.form("new_task"):
                c1, c2 = st.columns(2)
                t_title = c1.text_input("Title")
                all_emp_names = [e['name'] for e in EMPLOYEES]
                default_idx = all_emp_names.index(current_user['name'])
                t_assignee = c2.selectbox("Assignee", all_emp_names, index=default_idx)
                
                c3, c4 = st.columns(2)
                t_cat = c3.selectbox("Category", ["Admin", "Sales", "Logistics", "Tech"])
                t_est = c4.number_input("Est. Hours", 1.0)
                
                if st.form_submit_button("Create Task", type="primary"):
                    st.session_state.tasks.append({
                        "id": len(st.session_state.tasks)+1, 
                        "title": t_title, "assignee": t_assignee, "category": t_cat, "priority": "Medium", "status": "To Do",
                        "planned_date": str(datetime.date.today()), "est_time": t_est, "act_time": 0.0
                    })
                    st.success(f"Task Assigned!")
                    time.sleep(1)
                    safe_rerun()

    # 3. MASTER REGISTRY
    elif page == "Master Registry":
        st.markdown("## 🗂 Master Registry")
        st.dataframe(
            pd.DataFrame(st.session_state.tasks),
            use_container_width=True,
            hide_index=True,
            column_config={
                "status": st.column_config.SelectboxColumn("Status", options=["To Do", "In Progress", "Done"]),
                "act_time": st.column_config.ProgressColumn("Hours", min_value=0, max_value=10, format="%.1f")
            }
        )

    # 4. 3PL LOGISTICS
    elif page == "3PL Logistics":
        st.markdown("## 📦 Warehouse Control")
        
        col_log_1, col_log_2 = st.columns([3, 1])
        with col_log_2:
            if st.button("+ New Shipment", type="primary"):
                st.session_state.shipments.append({
                    "id": f"SH-{len(st.session_state.shipments)+1:03d}", "date": str(datetime.date.today()),
                    "am": current_user['name'], "dest": "Amazon FBA", "skus": "SKU-NEW", "qty": 0, "status": "New", "tracking": ""
                })
                safe_rerun()

        for ship in st.session_state.shipments:
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
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: st.caption(f"Items: {ship['skus']}")
            with c2: 
                if current_user['is_admin']:
                    new_stat = st.selectbox("Status", ["New", "Packing", "Shipped"], index=["New", "Packing", "Shipped"].index(ship['status']) if ship['status'] in ["New", "Packing", "Shipped"] else 0, key=f"sh_{ship['id']}", label_visibility="collapsed")
                    if new_stat != ship['status']:
                        ship['status'] = new_stat
                        safe_rerun()
                else:
                    st.info(ship['status'])
            st.markdown("---")

    # 5. AI ASSISTANT
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
                        context = f"Tasks: {st.session_state.tasks}\nShipments: {st.session_state.shipments}"
                        resp = ask_gemini(prompt, context)
                        st.write(resp)
                        st.session_state.messages.append({"role": "assistant", "content": resp})