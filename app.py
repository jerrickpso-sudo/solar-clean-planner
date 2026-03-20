import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import math
import datetime
from typing import Dict, List
import numpy as np

# ================= 页面配置 =================
st.set_page_config(
    page_title="巴西光伏运维 | 智能决策系统",
    page_icon="🇧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= 🎨 CSS 样式 =================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans SC', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #F5F5F7;
        color: #1D1D1F;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppHeader {display: none;}

    .stSidebar {
        background-color: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(0,0,0,0.05);
        padding-top: 2rem;
    }
    .stSidebar h2 { 
        font-size: 0.75rem; 
        text-transform: uppercase; 
        letter-spacing: 0.05em; 
        color: #86868b; 
        font-weight: 700; 
        margin-bottom: 0.5rem; 
        margin-top: 1rem;
    }
    
    .input-caption {
        font-size: 0.75rem;
        color: #6e6e73;
        margin-top: -10px;
        margin-bottom: 10px;
        line-height: 1.4;
    }
    
    .stButton > button {
        background-color: #FFFFFF;
        color: #0071e3;
        border: 1px solid #0071e3;
        border-radius: 980px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 0.85rem;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #0071e3;
        color: white;
        transform: scale(1.02);
    }
    
    .metric-container {
        background: #FFFFFF;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        border: 1px solid rgba(0,0,0,0.02);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        transition: transform 0.2s;
    }
    .metric-container:hover { transform: translateY(-3px); }
    .metric-label { font-size: 0.75rem; text-transform: uppercase; color: #86868b; font-weight: 700; margin-bottom: 6px; }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #1D1D1F; line-height: 1.1; }
    .metric-sub { font-size: 0.8rem; color: #34c759; font-weight: 500; margin-top: 4px; }
    .metric-sub.neutral { color: #86868b; }

    .weather-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        border: 1px solid rgba(0,0,0,0.02);
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    .w-date { font-size: 0.7rem; color: #86868b; font-weight: 700; text-transform: uppercase; }
    .w-icon { font-size: 2.2rem; margin: 6px 0; }
    .w-temp { font-size: 1rem; font-weight: 600; }
    .w-desc { font-size: 0.7rem; color: #86868b; margin: 2px 0 6px; }
    .w-stats { font-size: 0.65rem; background: #F5F5F7; padding: 3px 6px; border-radius: 6px; width: 100%; }
    .risk-badge { font-size: 0.6rem; font-weight: 700; padding: 2px 5px; border-radius: 3px; margin-top: 5px; text-transform: uppercase; }
    .risk-wind { background: #ffe5e5; color: #ff3b30; }
    .risk-mud { background: #fff4e5; color: #ff9500; }

    .fade-in-up { animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0; transform: translateY(15px); }
    @keyframes fadeInUp { to { opacity: 1; transform: translateY(0); } }

    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid #e5e5e5; }
</style>
""", unsafe_allow_html=True)

# ================= ⭐ 核心常数 =================
DEFAULT_PANEL_POWER_W = 700
MIN_PANEL_POWER_W = 300
MAX_PANEL_POWER_W = 900
WATER_CONSUMPTION_PER_PANEL = 0.015
ENERGY_CONSUMPTION_PER_PANEL = 0.008
ROBOT_EFFICIENCY_PANELS_PER_HOUR = 50
ROBOT_DAILY_WORK_HOURS = 10.0
ROBOT_AVAILABILITY_RATE = 0.95
DUST_ACCUMULATION_RATE_BASE = 0.4
MAX_DUST_CAPACITY = 15.0
SOILING_NON_LINEAR_FACTOR = 1.2
HOTSPOT_THRESHOLD = 8.0
HEAVY_RAIN_THRESHOLD = 5.0
LIGHT_RAIN_THRESHOLD = 1.0
MUD_RISK_HUMIDITY = 85.0
WIND_SAFETY_LIMIT = 10.0
CARBON_FACTOR = 0.58

# ================= 🗄️ 数据库 =================
STATION_DB = {
    "请选择电站...": {},
    "AUT (Autazes)": {"lat": -3.60, "lon": -59.12, "sell_price": 0.35, "robot_elec_price": 0.25, "water_price": 2.0},
    "NOD (Nova Olinda)": {"lat": -3.88, "lon": -59.07, "sell_price": 0.38, "robot_elec_price": 0.28, "water_price": 2.2},
    "BBA (Borba)": {"lat": -4.40, "lon": -59.63, "sell_price": 0.32, "robot_elec_price": 0.22, "water_price": 1.8},
    "HMT (Humaita)": {"lat": -7.48, "lon": -63.02, "sell_price": 0.40, "robot_elec_price": 0.35, "water_price": 2.5},
    "SGC (Sao Gabriel)": {"lat": -0.15, "lon": -67.03, "sell_price": 0.36, "robot_elec_price": 0.26, "water_price": 2.1}
}

# ================= 🛠️ 工具函数 =================
def get_weather_icon(code: int) -> str:
    icons = {0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 51: "🌦️", 53: "🌦️", 55: "🌧️", 
             61: "🌧️", 63: "🌧️", 65: "⛈️", 80: "🌦️", 81: "🌧️", 82: "⛈️", 95: "⚡", 96: "⚡", 99: "⚡"}
    return icons.get(code, "❓")

def get_weather_desc(code: int, humidity: float, wind: float) -> str:
    base = {0: "晴朗", 1: "大部晴朗", 2: "多云", 3: "阴天", 45: "雾", 51: "小雨", 
            53: "雨", 55: "雨", 61: "雨", 63: "雨", 65: "大雨", 80: "阵雨", 
            81: "雨", 82: "风暴", 95: "雷暴", 96: "雷暴", 99: "雷暴"}.get(code, "未知")
    risks = []
    if code in [95, 96, 99]: risks.append("⚡")
    if wind > WIND_SAFETY_LIMIT: risks.append(f"💨{wind:.0f}")
    if humidity > MUD_RISK_HUMIDITY and code in [2, 3]: risks.append("💧")
    return f"{base} ({' '.join(risks)})" if risks else base

def fmt_date_short(s):
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}"
    except: return s

def fmt_date_full(s):
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d")
        return f"{dt.year}.{dt.month:02d}.{dt.day:02d}"
    except: return s

def validate_inputs(count, power):
    cap = (count * power) / 1_000_000
    valid = True
    err = ""
    if power < MIN_PANEL_POWER_W or power > MAX_PANEL_POWER_W:
        valid = False
        err = f"功率超出范围 ({MIN_PANEL_POWER_W}-{MAX_PANEL_POWER_W}W)"
    return valid, err, round(cap, 2)

# ================= 🌐 数据获取 =================
@st.cache_data(ttl=1800)
def fetch_weather(lat, lon, days=14):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "weathercode,temperature_2m,relativehumidity_2m,windspeed_10m,rain",
            "daily": "shortwave_radiation_sum,precipitation_sum,windspeed_10m_max,temperature_2m_max",
            "timezone": "auto", "forecast_days": days
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        h, d = data['hourly'], data['daily']
        agg = {}
        for i in range(len(h['time'])):
            date = h['time'][i].split('T')[0]
            if date not in agg: agg[date] = {"r":0, "w":0, "h":0, "t":0, "c":[]}
            agg[date]["r"] += h['rain'][i] or 0
            agg[date]["w"] = max(agg[date]["w"], h['windspeed_10m'][i] or 0)
            agg[date]["h"] = max(agg[date]["h"], h['relativehumidity_2m'][i] or 50)
            agg[date]["t"] = max(agg[date]["t"], h['temperature_2m'][i] or 25)
            agg[date]["c"].append(h['weathercode'][i] or 0)
            
        res = []
        for i in range(len(d['time'])):
            date = d['time'][i]
            info = agg.get(date, {})
            rad_mj = d['shortwave_radiation_sum'][i] or 0
            rain = d['precipitation_sum'][i] or info.get("r", 0)
            wind = (d['windspeed_10m_max'][i] or info.get("w", 0)) / 3.6
            temp = d['temperature_2m_max'][i] or info.get("t", 25)
            hum = info.get("h", 70)
            code = max(set(info.get("c", [0])), key=info.get("c", [0]).count)
            
            res.append({
                "date": date, "rain": round(rain, 1), "wind": round(wind, 1),
                "radiation_mj": round(rad_mj, 1),
                "radiation_kwh": round(rad_mj / 3.6, 2),
                "humidity": round(hum, 1), "temp": round(temp, 1),
                "code": code, "icon": get_weather_icon(code), "desc": get_weather_desc(code, hum, wind)
            })
        return res, "Open-Meteo API"
    except Exception as e:
        start = datetime.datetime.now()
        sim = []
        for i in range(days):
            d = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            r = np.random.exponential(3) if np.random.random() < 0.6 else 0
            w = max(0, np.random.normal(4, 2))
            rad_mj = max(5, 20 * (1 - min(r/10, 0.8)) + np.random.normal(0, 2))
            hum = min(99, max(40, np.random.normal(80, 10)))
            code = 61 if r > 1 else (3 if hum > 85 else 0)
            sim.append({
                "date": d, "rain": round(r, 1), "wind": round(w, 1), 
                "radiation_mj": round(rad_mj, 1), "radiation_kwh": round(rad_mj/3.6, 2),
                "humidity": round(hum, 1), "temp": round(np.random.normal(30, 3), 1),
                "code": code, "icon": get_weather_icon(code), "desc": get_weather_desc(code, hum, w)
            })
        return sim, "模拟模式 (API 备用)"

# ================= 🧠 决策引擎 =================
def run_engine(weather, cfg, econ):
    dates = [x['date'] for x in weather]
    rains = [x['rain'] for x in weather]
    winds = [x['wind'] for x in weather]
    rads_mj = [x['radiation_mj'] for x in weather]
    hums = [x['humidity'] for x in weather]
    
    panels = cfg['panels']
    cap_mw = cfg['capacity']
    robots = cfg['robots']
    
    p_sell, p_water, p_elec = econ['sell'], econ['water'], econ['elec']
    
    eff_robots = robots * ROBOT_AVAILABILITY_RATE
    daily_cap = eff_robots * ROBOT_EFFICIENCY_PANELS_PER_HOUR * ROBOT_DAILY_WORK_HOURS
    
    if daily_cap <= 0:
        duration = 999
    else:
        duration = math.ceil(panels / daily_cap)
    
    water_cost = panels * WATER_CONSUMPTION_PER_PANEL * p_water
    elec_cost = panels * ENERGY_CONSUMPTION_PER_PANEL * p_elec
    single_cost = water_cost + elec_cost
    
    dust = 0.0
    plan, windows = [], []
    last_end = -999
    
    for i in range(len(dates)):
        r, w, rad_mj, hum = rains[i], winds[i], rads_mj[i], hums[i]
        
        if r >= HEAVY_RAIN_THRESHOLD: dust = 0.0
        elif r >= LIGHT_RAIN_THRESHOLD: dust *= 0.5
        else:
            rate = DUST_ACCUMULATION_RATE_BASE
            if hum > MUD_RISK_HUMIDITY and r < 0.1: rate *= 1.3
            dust += rate
        dust = min(dust, MAX_DUST_CAPACITY)
        
        loss = (dust / 100) * (1 + (1 - rad_mj/20) * (SOILING_NON_LINEAR_FACTOR - 1))
        loss = min(loss, 1.0)
        
        gen_potential = cap_mw * (rad_mj / 3.6) * 1000
        lost_rev = gen_potential * loss * p_sell
        
        is_cleaning = i <= last_end and i >= (last_end - duration + 1)
        safety_stop = w > WIND_SAFETY_LIMIT
        hot_spot = dust > HOTSPOT_THRESHOLD
        
        action, status, cost = "监控", "⚪ 正常运行", 0.0
        trigger, reason = False, ""
        
        if not is_cleaning and not safety_stop:
            if hot_spot:
                trigger, reason = True, "热斑风险"
            elif lost_rev * 3.0 > single_cost * 1.1:
                trigger, reason = True, "经济最优"
        
        if trigger and (i + duration < len(dates)):
            action, cost = "清洗", single_cost
            last_end = i + duration - 1
            status = f"🧹 清洗中 ({reason})"
            windows.append({"start": i, "end": last_end, "reason": reason, "cost": single_cost})
        
        if i > 0 and (i-1) in [w['end'] for w in windows]:
            dust, loss = 0.2, 0.002
            status = "✨ 高效发电"
            
        actual_gen = gen_potential * (1 - loss)
        net = actual_gen * p_sell - cost
        
        plan.append({
            "date": dates[i], "rain": r, "wind": w, 
            "radiation_kwh": round(rad_mj / 3.6, 2),
            "dust": round(dust, 2), "loss": round(loss*100, 1),
            "action": action, "status": status,
            "revenue": round(actual_gen * p_sell, 1), "cost": round(cost, 1),
            "net": round(net, 1), "carbon": round((actual_gen * CARBON_FACTOR)/1000, 3),
            "hot_spot": hot_spot, "safety": safety_stop
        })
        if action == "Cleaning" and i == last_end: dust = 0.2
        
    return pd.DataFrame(plan), windows, {
        "total_cost": sum(w['cost'] for w in windows),
        "count": len(windows), "duration": duration
    }

# ================= 🪟 定义原生对话框 =================
@st.dialog("📖 技术原理")
def technical_principles_dialog():
    st.markdown("""
    本系统结合实时气象预报与非线性物理模型，优化巴西光伏电站的清洗调度。
    
    #### 1. 数据来源
    - **天气:** [Open-Meteo API](https://open-meteo.com/) (全球预报模型)。
    - **指标:** 短波辐射 (kWh/m²)、降水、风速、湿度。
    
    #### 2. 积灰累积模型
    <div class="formula" style="background:#fbfbfd; border-left:4px solid #0071e3; padding:10px; margin:10px 0;">
        Dust<sub>t+1</sub> = min(Dust<sub>t</sub> + Rate × Factor, Max<sub>cap</sub>)
    </div>
    - `Rate`: 0.4%/天 (基础)，若湿度 > 85% 则乘以 1.3 (泥泞风险)。
    - **自然清洗:** 降雨 > 5mm 重置积灰；降雨 > 1mm 减少 50%。
    
    #### 3. 功率损耗模型
    <div class="formula" style="background:#fbfbfd; border-left:4px solid #0071e3; padding:10px; margin:10px 0;">
        Loss = (Dust / 100) × [1 + (1 - Rad/Rad<sub>std</sub>) × 1.2]
    </div>
    
    #### 4. 经济决策逻辑
    触发清洗条件：
    1. **安全:** 积灰 > 8% (热斑风险) 且 风速 < 10 m/s。
    2. **经济:** 损失收入 > 1.1 × 清洗成本。
    
    *注：水资源限制已禁用。机器人数量直接影响清洗窗口期长短。*
    """, unsafe_allow_html=True)

# ================= 🖥️ 界面布局 =================

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/solar-panel.png", width=50)
    st.title("系统配置")
    st.markdown("---")
    
    station = st.selectbox("电站选择", list(STATION_DB.keys()), index=0)
    
    if station != "请选择电站...":
        db = STATION_DB[station]
        
        st.markdown("## 规模参数")
        c1, c2 = st.columns(2)
        with c1: 
            p_count = st.number_input("光伏板数量", value=40000, step=100, label_visibility="collapsed")
            st.caption("电站光伏板总数。决定总清洗工作量。")
        with c2: 
            p_power = st.number_input("单板功率 (Wp)", value=700, step=10, label_visibility="collapsed")
            st.caption("每块板的峰值功率 (瓦特)。用于计算总装机容量。")
        
        valid, err, cap_mw = validate_inputs(p_count, p_power)
        if not valid:
            st.error(err)
            st.stop()
        
        st.info(f"**光伏总负载：{cap_mw:.2f} MW**", icon="🔋")
        
        st.markdown("## 清洗资源")
        robots = st.number_input("清洗机器人数量 (台)", value=28, step=1, label_visibility="collapsed")
        st.caption("可用清洗机器人数量。机器人越多 = 清洗周期越短 = 调度越灵活。")
        
        target_days = 7
        daily_need = p_count / target_days
        robot_capacity_per_day = ROBOT_EFFICIENCY_PANELS_PER_HOUR * ROBOT_DAILY_WORK_HOURS * ROBOT_AVAILABILITY_RATE
        rec_robots = math.ceil(daily_need / robot_capacity_per_day) if robot_capacity_per_day > 0 else 999
        
        current_days = math.ceil(p_count / (robots * robot_capacity_per_day)) if (robots * robot_capacity_per_day) > 0 else 999
        
        if robots < rec_robots:
            st.warning(f"⚠️ 数量不足：建议 **{rec_robots} 台** 以实现 {target_days} 天清洗周期。")
            st.caption(f"影响：当前配置需 **{current_days} 天** 完成清洗。周期过长可能错过最佳天气窗口。")
        elif robots > rec_robots:
            st.success(f"✅ 配置优良：超过推荐值 ({rec_robots} 台)。")
            st.caption(f"影响：清洗迅速 (约 **{current_days} 天**)。允许频繁维护，更好地管理风险。")
        else:
            st.info(f"✅ 推荐数量 ({rec_robots} 台)。周期：约 {current_days} 天。")
        
        st.markdown("## 经济参数 (巴西雷亚尔)")
        p_sell = st.number_input("售电电价 (R$/kWh)", value=float(db['sell_price']), format="%.3f", label_visibility="collapsed")
        st.caption("每千瓦时电力出售给电网的收入。")
        
        p_elec = st.number_input("机器人耗电成本 (R$/kWh)", value=float(db['robot_elec_price']), format="%.3f", label_visibility="collapsed")
        st.caption("清洗机器人运行时的电力消耗成本。")
        
        p_water = st.number_input("工业用水成本 (R$/吨)", value=float(db['water_price']), format="%.2f", label_visibility="collapsed")
        st.caption("清洗所用的工业水成本（如适用）。")
        
        st.markdown("---")
        st.button("📖 技术原理", use_container_width=True, on_click=technical_principles_dialog)
        
        LAT, LON = float(db['lat']), float(db['lon'])
        run = True
    else:
        run = False

if run:
    weather_data, source = fetch_weather(LAT, LON)
    cfg = {"panels": p_count, "capacity": cap_mw, "robots": robots}
    econ = {"sell": p_sell, "water": p_water, "elec": p_elec}
    
    df, wins, stats = run_engine(weather_data, cfg, econ)
    
    st.title(f"🇧 {station}")
    st.caption(f"数据来源：{source} | 更新时间：{datetime.datetime.now().strftime('%H:%M')}")
    st.markdown("---")
    
    c0, c1, c2, c3, c4 = st.columns(5)
    rev = df['revenue'].sum()
    cost = stats['total_cost']
    profit = rev - cost
    carbon = df['carbon'].sum()
    
    with c0:
        st.markdown(f"""
        <div class="metric-container fade-in-up">
            <div class="metric-label">光伏总负载</div>
            <div class="metric-value">{cap_mw:.2f} MW</div>
            <div class="metric-sub neutral">装机容量</div>
        </div>
        """, unsafe_allow_html=True)
    with c1:
        st.markdown(f"""
        <div class="metric-container fade-in-up" style="animation-delay: 0.1s">
            <div class="metric-label">总收入</div>
            <div class="metric-value">R$ {rev:,.0f}</div>
            <div class="metric-sub neutral">14 天预测</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-container fade-in-up" style="animation-delay: 0.2s">
            <div class="metric-label">清洗成本</div>
            <div class="metric-value">R$ {cost:,.0f}</div>
            <div class="metric-sub neutral">{stats['count']} 个周期</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        margin = (profit/max(rev,1))*100
        color = "#34c759" if margin > 0 else "#ff3b30"
        st.markdown(f"""
        <div class="metric-container fade-in-up" style="animation-delay: 0.3s">
            <div class="metric-label">净利润</div>
            <div class="metric-value">R$ {profit:,.0f}</div>
            <div class="metric-sub" style="color:{color}">{margin:.1f}% 利润率</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-container fade-in-up" style="animation-delay: 0.4s">
            <div class="metric-label">碳减排</div>
            <div class="metric-value">{carbon:,.2f} 吨</div>
            <div class="metric-sub neutral">CO₂e 当量</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.subheader("天气预报与风险")
    rows = (len(weather_data) + 6) // 7
    for r in range(rows):
        cols = st.columns(7)
        for c in range(7):
            idx = r * 7 + c
            if idx < len(weather_data):
                d = weather_data[idx]
                badge = ""
                if d['wind'] > WIND_SAFETY_LIMIT: badge = "<div class='risk-badge risk-wind'>大风</div>"
                elif d['humidity'] > MUD_RISK_HUMIDITY and d['code'] in [2,3]: badge = "<div class='risk-badge risk-mud'>泥泞</div>"
                
                with cols[c]:
                    st.markdown(f"""
                    <div class="weather-card fade-in-up" style="animation-delay: {idx*0.05}s">
                        <div class="w-date">{fmt_date_short(d['date'])}</div>
                        <div class="w-icon">{d['icon']}</div>
                        <div class="w-temp">{d['temp']}°C</div>
                        <div class="w-desc">{d['desc'].split('(')[0]}</div>
                        <div class="w-stats">🌧️ {d['rain']}mm | ☢️ {d['radiation_kwh']} kWh</div>
                        {badge}
                    </div>
                    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 📈 图表：三轴分离 (最终稳定版 - 不使用 position)
    st.subheader("策略可视化")
    fig = go.Figure()
    
    # 1. 辐射量 (左轴 y1)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['radiation_kwh'], 
        name='辐射量 (kWh/m²)', 
        line=dict(color='#ff9500', width=3),
        yaxis='y1'
    ))
    
    # 2. 积灰度 (右轴 y2 - 内侧)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['dust'], 
        name='积灰度 (%)', 
        line=dict(color='#ff3b30', width=3),
        yaxis='y2'
    ))
    
    # 3. 净现金流 (右轴 y3 - 外侧)
    fig.add_trace(go.Bar(
        x=df['date'], y=df['net'], 
        name='净现金流 (R$)', 
        marker_color=df['net'].apply(lambda x: '#34c759' if x>0 else '#ff3b30'), 
        opacity=0.4,
        yaxis='y3'
    ))
    
    # 添加清洗窗口背景
    for w in wins:
        fig.add_vrect(x0=df['date'].iloc[w['start']], x1=df['date'].iloc[w['end']], fillcolor="#0071e3", opacity=0.1, line_width=0)
    
    # 🔧 关键修复：通过 domain 和 margin 分离坐标轴
    fig.update_layout(
        height=550,
        hovermode='x unified',
        legend=dict(orientation="h", y=1.02, x=0.5, xanchor='center', font=dict(size=11)),
        
        # 左轴 (辐射)
        yaxis=dict(
            title="辐射量 (kWh/m²)", 
            side='left', 
            gridcolor='#f0f0f0', 
            range=[0, 8], 
            tickfont=dict(color="#ff9500", size=11),
            title_standoff=10
        ),
        
        # 右轴 1 (积灰 - 内侧)
        yaxis2=dict(
            title="积灰度 (%)", 
            overlaying='y', 
            side='right', 
            showgrid=False, 
            range=[0, 15], 
            tickfont=dict(color="#ff3b30", size=11),
            anchor='free',
            domain=[0, 1],
            # 不再使用 position，让 Plotly 自动放置在右侧边缘
        ),
        
        # 右轴 2 (现金流 - 外侧)
        yaxis3=dict(
            title="净现金流 (R$)", 
            overlaying='y', 
            side='right', 
            showgrid=False, 
            tickfont=dict(color="#34c759", size=11),
            anchor='free',
            domain=[0, 1],
            # 不再使用 position
        ),
        
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        # 大幅增加右侧边距，为两个轴留出空间
        margin=dict(l=60, r=120, t=60, b=40), 
        font=dict(family="Noto Sans SC", size=11),
        barmode='overlay'
    )

    st.plotly_chart(fig, use_container_width=True)
    
    # 表格
    st.subheader("执行计划")
    mode = st.radio("筛选", ["全部", "仅清洗", "仅风险"], horizontal=True)
    view = df.copy()
    view['Date'] = view['date'].apply(fmt_date_full)
    
    if mode == "仅清洗": view = view[view['action'] == '清洗']
    elif mode == "仅风险": view = view[(view['hot_spot']) | (view['safety'])]
    
    cols_disp = ["Date", "radiation_kwh", "dust", "loss", "action", "status", "net"]
    rename_map = {"radiation_kwh": "辐射 (kWh)", "dust": "积灰%", "loss": "损耗%", "action": "动作", "status": "状态", "net": "净收益 (R$)"}
    
    def style_status(val):
        if "风险" in str(val): return "color:white; background-color:#ff3b30;"
        if "清洗" in str(val): return "color:white; background-color:#0071e3;"
        if "高效" in str(val): return "color:#34c759; font-weight:bold;"
        return ""
    
    st.dataframe(
        view[cols_disp].rename(columns=rename_map).style.map(style_status, subset=['状态'])
        .format({"辐射 (kWh)":"{:.2f}", "积灰%":"{:.1f}%", "损耗%":"{:.1f}%", "净收益 (R$)":"R$ {:,.0f}"}),
        use_container_width=True, height=300
    )

else:
    st.markdown("""
    <div style="text-align:center; padding: 100px; color: #86868b;">
        <h2>请选择电站开始分析</h2>
        <p>系统将自动计算最优清洗策略。</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2026 巴西光伏智能运维 | Designed by Jerrick Tan_N184")
