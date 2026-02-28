import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import math
import datetime

# ================= 页面配置 =================
st.set_page_config(
    page_title="光伏电站季度固定清洗计划与智能优选",
    page_icon="📅",
    layout="wide"
)

# ================= ⭐ 行业常数与物理模型 ⭐
ROBOT_EFFICIENCY_MW_PER_DAY = 0.8
PANEL_POWER_W = 700
WATER_CONSUMPTION_PER_MW = 10.0
ENERGY_CONSUMPTION_PER_MW = 5.0
DUST_ACCUMULATION_RATE = 0.4
RAIN_CLEANING_THRESHOLD = 5.0
RAIN_CLEANING_EFFICIENCY = 0.9
MAX_DUST_CAPACITY = 15.0

# ================= 核心数据库 =================
STATION_DB = {
    "请选择电站...": {},
    "AUT (Autazes)": {"lat": -3.60, "lon": -59.12, "sell_price": 0.35, "robot_elec_price": 0.25, "water_price": 2.0, "pollution_index": 0.6, "robot_efficiency": 0.90},
    "NOD (Nova Olinda)": {"lat": -3.88, "lon": -59.07, "sell_price": 0.38, "robot_elec_price": 0.28, "water_price": 2.2, "pollution_index": 0.7, "robot_efficiency": 0.88},
    "BBA (Borba)": {"lat": -4.40, "lon": -59.63, "sell_price": 0.32, "robot_elec_price": 0.22, "water_price": 1.8, "pollution_index": 0.5, "robot_efficiency": 0.92},
    "HMT (Humaita)": {"lat": -7.48, "lon": -63.02, "sell_price": 0.40, "robot_elec_price": 0.35, "water_price": 2.5, "pollution_index": 0.8, "robot_efficiency": 0.85},
    "SGC (Sao Gabriel)": {"lat": -0.15, "lon": -67.03, "sell_price": 0.36, "robot_elec_price": 0.26, "water_price": 2.1, "pollution_index": 0.65, "robot_efficiency": 0.89}
}

# ================= 侧边栏 =================
st.sidebar.image("https://img.icons8.com/color/96/solar-panel.png", width=80)
st.sidebar.header("📅 季度固定周期规划")

selected_station = st.sidebar.selectbox("📍 选择目标电站", list(STATION_DB.keys()), index=0)

# 初始化侧边栏参数监控
if 'last_params' not in st.session_state:
    st.session_state.last_params = {}

current_params = {
    'station': selected_station,
    'capacity': 0,
    'robots': 0,
    'dust_rate': 0
}

if selected_station != "请选择电站...":
    data = STATION_DB[selected_station]
    st.sidebar.subheader("⚙️ 电站规模与配置")
    capacity_mw = st.sidebar.number_input("⚡ 装机容量 (MW)", value=23.35, min_value=0.1, step=0.1)
    total_panels = int((capacity_mw * 1_000_000) / PANEL_POWER_W)
    st.sidebar.success(f"**🔢 太阳能板数量**: {total_panels:,} 块")
    
    robot_count = st.sidebar.number_input("🚜 可用机器人数量 (台)", value=5, min_value=1, step=1)
    daily_capacity = robot_count * ROBOT_EFFICIENCY_MW_PER_DAY
    days_to_clean_all = math.ceil(capacity_mw / daily_capacity) if daily_capacity > 0 else 999
    st.sidebar.info(f"💡 **清洗能力**: {daily_capacity:.1f} MW/天\n**单次全站工期**: **{days_to_clean_all} 天**")

    st.sidebar.subheader("⚖️ 积灰模型参数")
    poll_idx = float(data['pollution_index'])
    effective_dust_rate = st.sidebar.slider("🌫️ 日均积灰速率 (%/天)", 0.1, 1.0, DUST_ACCUMULATION_RATE * poll_idx, 0.1)
    
    st.sidebar.subheader("💵 关键经济参数")
    sell_price = st.sidebar.number_input("☀️ 太阳能产电收益 (元/kWh)", value=float(data['sell_price']), step=0.01, format="%.2f")
    robot_elec_price = st.sidebar.number_input("🔌 清洗用电单价 (元/kWh)", value=float(data['robot_elec_price']), step=0.01, format="%.2f")
    water_price = st.sidebar.number_input("💧 清洗用水单价 (元/吨)", value=float(data['water_price']), step=0.1, format="%.1f")
    
    robot_eff = float(data['robot_efficiency'])
    LATITUDE = float(data['lat'])
    LONGITUDE = float(data['lon'])
    
    # 更新当前参数用于比对
    current_params['capacity'] = capacity_mw
    current_params['robots'] = robot_count
    current_params['dust_rate'] = effective_dust_rate
else:
    st.stop()

# ================= 核心逻辑：参数变更检测 =================
# 检查侧边栏参数是否发生变化
params_changed = False
if st.session_state.last_params != current_params:
    params_changed = True
    st.session_state.last_params = current_params.copy()
    # 如果参数变了，清除旧数据和过滤状态，强制重置
    if 'data_loaded' in st.session_state:
        del st.session_state['data_loaded']
        del st.session_state['df_daily']
        del st.session_state['rec_windows']
    if 'filter_option' in st.session_state:
        del st.session_state['filter_option']

# ================= 主界面 =================
st.title(f"📅 {selected_station} - 季度固定清洗计划与智能优选")
st.markdown(f"**容量**: {capacity_mw} MW | **机器人**: {robot_count} 台 | **单次工期**: {days_to_clean_all} 天")
st.info(f"""
**🏢 公司合规策略**:
1. **固定频次**: 严格执行 **每季度清洗一次** (全年共4次)。
2. **智能优选**: 在每个季度内，自动扫描并推荐 **连续{days_to_clean_all}天无暴雨 (<10mm)** 且 **积灰度最高** 的最佳时间段。
""")

# ================= 核心逻辑函数 =================

@st.cache_data(ttl=3600)
def get_real_historical_climate(lat, lon):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily": ["precipitation_sum", "wind_speed_10m_max"],
        "timezone": "America/Manaus"
    }
    try:
        with st.spinner("正在下载过去365天逐日实测数据..."):
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if 'daily' not in data or 'precipitation_sum' not in data['daily']:
                return None
            real_rain = data['daily']['precipitation_sum']
            real_wind = data['daily']['wind_speed_10m_max']
            if len(real_rain) < 300: return None
            future_start = datetime.datetime.now() + datetime.timedelta(days=1)
            future_dates = [(future_start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(len(real_rain))]
            return {"time": future_dates, "precipitation_sum": real_rain, "wind_speed_10m_max": real_wind}
    except Exception as e:
        return None

def analyze_quarterly_plan(weather_data, capacity, p_sell, p_elec, p_water, dust_rate, r_eff, clean_duration):
    dates = weather_data['time']
    rain = weather_data['precipitation_sum']
    RAIN_THRESHOLD = 10.0
    total_cleaning_cost = (capacity * WATER_CONSUMPTION_PER_MW) * p_water + (capacity * ENERGY_CONSUMPTION_PER_MW) * p_elec
    
    date_objs = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates]
    step = len(dates) // 4
    q_ranges = [(0, step-1), (step, 2*step-1), (2*step, 3*step-1), (3*step, len(dates)-1)]
    
    daily_plans = []
    recommended_windows = []
    chosen_days = set()
    
    # 预计算积灰
    dust_series = []
    current_dust = 0.0
    for i in range(len(dates)):
        if rain[i] > RAIN_CLEANING_THRESHOLD: current_dust *= (1 - RAIN_CLEANING_EFFICIENCY)
        elif rain[i] > 1.0: current_dust *= 0.8
        if rain[i] <= RAIN_CLEANING_THRESHOLD: current_dust += dust_rate
        current_dust = min(current_dust, MAX_DUST_CAPACITY)
        dust_series.append(current_dust)

    # 寻找窗口
    for idx, (q_start, q_end) in enumerate(q_ranges):
        best_start = -1
        best_score = -1
        best_avg_dust = 0
        is_perfect = False
        
        for start in range(q_start, q_end - clean_duration + 1):
            end = start + clean_duration - 1
            is_safe = True
            max_rain = 0
            for k in range(start, end + 1):
                if rain[k] > RAIN_THRESHOLD:
                    is_safe = False
                    break
                max_rain = max(max_rain, rain[k])
            
            if is_safe:
                is_perfect = True
                avg_dust = sum(dust_series[k] for k in range(start, end+1)) / clean_duration
                score = avg_dust * 10 + (10 - max_rain)
                if score > best_score:
                    best_score = score
                    best_start = start
                    best_avg_dust = avg_dust
        
        if best_start == -1: # 无完美窗口，选雨最小的
            min_rain_sum = 99999
            for start in range(q_start, q_end - clean_duration + 1):
                r_sum = sum(rain[k] for k in range(start, start+clean_duration))
                if r_sum < min_rain_sum:
                    min_rain_sum = r_sum
                    best_start = start
            avg_dust = sum(dust_series[k] for k in range(best_start, best_start+clean_duration))/clean_duration
        else:
            avg_dust = best_avg_dust
            
        for k in range(best_start, best_start + clean_duration): chosen_days.add(k)
        
        recommended_windows.append({
            'q': idx + 1, 'start_idx': best_start, 'end_idx': best_start + clean_duration - 1,
            'start_date': dates[best_start], 'end_date': dates[best_start + clean_duration - 1],
            'avg_dust': avg_dust, 'cost': total_cleaning_cost, 'is_perfect': is_perfect
        })

    # 生成每日表
    for i in range(len(dates)):
        date_obj = date_objs[i]
        weekday_cn = date_obj.strftime("%A")
        wk_map = {"Monday":"周一", "Tuesday":"周二", "Wednesday":"周三", "Thursday":"周四", "Friday":"周五", "Saturday":"周六", "Sunday":"周日"}
        
        is_rec = i in chosen_days
        q_info = next((w for w in recommended_windows if w['start_idx'] <= i <= w['end_idx']), None)
        
        if is_rec and q_info:
            status = f"📅 Q{q_info['q']} 推荐" if q_info['is_perfect'] else f"⚠️ Q{q_info['q']} 高风险"
            color = "green" if q_info['is_perfect'] else "red"
            action = "Scheduled Cleaning"
            profit = -total_cleaning_cost if i == q_info['start_idx'] else 0
        else:
            d_val = dust_series[i]
            loss = (d_val * r_eff / 100.0) * (capacity * 1000.0 * 5.0) * p_sell
            status = "⚪ 积灰较少" if d_val < 3.0 else "⚠️ 积灰累积中"
            color = "gray" if d_val < 3.0 else "orange"
            action = "Monitor"
            profit = -loss

        daily_plans.append({
            "日期": dates[i], "星期": wk_map.get(weekday_cn, ""), "季度": (i // step) + 1,
            "实测降雨 (mm)": round(rain[i], 1), "动态积灰度 (%)": round(dust_series[i], 1),
            "操作建议": status, "状态颜色": color, "行动": action,
            "当日净现金流 ($)": round(profit, 1), "month_num": date_obj.month
        })
        
    return pd.DataFrame(daily_plans), recommended_windows, RAIN_THRESHOLD

# ================= 执行与展示 =================

if st.button("🔍 生成季度固定清洗计划", type="primary"):
    weather = get_real_historical_climate(LATITUDE, LONGITUDE)
    
    if weather:
        st.success(f"✅ **规划就绪**: 已划分4个季度并优选最佳窗口。")
        df_daily, rec_windows, RAIN_THRESHOLD = analyze_quarterly_plan(
            weather, capacity_mw, sell_price, robot_elec_price, water_price, 
            effective_dust_rate, robot_eff, days_to_clean_all
        )
        
        # 将数据存入 session_state
        st.session_state['df_daily'] = df_daily
        st.session_state['rec_windows'] = rec_windows
        st.session_state['data_loaded'] = True
        # 注意：这里不设置 filter_option，让它保持用户之前的选择（如果有）
        # 如果是因为侧边栏变化导致的数据清空，上面的检测逻辑已经删除了 filter_option
        # 如果是首次加载，下面的逻辑会初始化它

# 从 session_state 读取数据（如果存在）
if 'data_loaded' in st.session_state and st.session_state['data_loaded']:
    df_daily = st.session_state['df_daily']
    rec_windows = st.session_state['rec_windows']
    
    # --- 顶部统计 ---
    st.subheader("📊 年度季度清洗计划概览")
    cols = st.columns(4)
    total_cost = 0
    for i, w in enumerate(rec_windows):
        total_cost += w['cost']
        if i < 4:
            date_range = f"{w['start_date'][5:]} ~ {w['end_date'][5:]}"
            detail = f"积灰:{w['avg_dust']:.1f}% | 成本:${w['cost']:,.0f}"
            with cols[i]:
                if w['is_perfect']:
                    st.metric(f"🗓️ Q{i+1}", date_range, help=detail)
                    st.success(f"**推荐窗口**\n{detail}", icon="✅")
                else:
                    st.metric(f"🗓️ Q{i+1}", date_range, help=detail)
                    st.error(f"**高风险窗口**\n{detail}", icon="⚠️")
    
    st.info(f"**💰 年度预估总清洗成本**: ${total_cost:,.1f}")
    st.divider()
    
    # --- 表格 (智能状态管理) ---
    st.subheader("📅 季度固定清洗执行计划表")
    
    filter_options = ["显示所有日期", "仅显示 📅 推荐清洗期", "仅显示 ⚠️ 高风险清洗期"]
    
    # 初始化：只有当 filter_option 不存在时才设为默认值
    if 'filter_option' not in st.session_state:
        st.session_state.filter_option = filter_options[0]
    
    # 使用 radio 组件，绑定 key
    selected_filter = st.radio(
        "🔍 视图过滤:", 
        filter_options, 
        horizontal=True,
        key='filter_option'
    )
    
    # 根据选择过滤数据
    display_df = df_daily.copy()
    if selected_filter == "仅显示 📅 推荐清洗期":
        display_df = display_df[(display_df['行动'] == "Scheduled Cleaning") & (display_df['状态颜色'] == 'green')]
    elif selected_filter == "仅显示 ⚠️ 高风险清洗期":
        display_df = display_df[(display_df['行动'] == "Scheduled Cleaning") & (display_df['状态颜色'] == 'red')]
    
    def color_code(val):
        if "推荐" in val: return "color: white; font-weight: bold; background-color: #16a34a;"
        if "高风险" in val: return "color: white; font-weight: bold; background-color: #dc2626;"
        if "较少" in val: return "color: gray; background-color: #f3f4f6;"
        if "累积" in val: return "color: orange; background-color: #ffedd5;"
        return ""
    
    st.dataframe(
        display_df.style.applymap(color_code, subset=['操作建议'])
        .format({"当日净现金流 ($)": "${:.1f}", "动态积灰度 (%)": "{:.1f}%"}), 
        use_container_width=True, 
        hide_index=True, 
        height=400
    )
    
    csv = display_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载季度计划 CSV", data=csv, file_name='quarterly_plan.csv', mime='text/csv')
    st.divider()
    
    # --- 可视化 ---
    st.subheader("📈 全年积灰趋势与季度固定清洗窗口")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_daily['日期'], y=df_daily['动态积灰度 (%)'],
        mode='lines', name='动态积灰度 (%)',
        line=dict(color='purple', width=2),
        fill='tozeroy', fillcolor='rgba(128, 0, 128, 0.1)'
    ))
    
    has_perfect = any(w['is_perfect'] for w in rec_windows)
    has_risk = any(not w['is_perfect'] for w in rec_windows)
    
    for w in rec_windows:
        color = 'green' if w['is_perfect'] else 'red'
        fig.add_vrect(
            x0=w['start_date'], 
            x1=w['end_date'],
            fillcolor=color, 
            opacity=0.25,
            line_width=0
        )
    
    fig.update_layout(
        height=500, margin=dict(l=0, r=0, t=30, b=0),
        xaxis_title="日期", yaxis_title="积灰度 (%)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickformat="%m-%d", tickangle=45, nticks=36)
    )
    
    if has_perfect:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='green', size=10), name='✅ 推荐窗口 (少雨/高积灰)', hoverinfo='skip'))
    if has_risk:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color='red', size=10), name='⚠️ 高风险窗口 (多雨/强制清洗)', hoverinfo='skip'))
        
    st.plotly_chart(fig, use_container_width=True)
    
    st.caption("""
    **图表解读**:
    - **紫色曲线**: 全年积灰自然累积趋势。
    - **绿色阴影区域**: 系统推荐的**季度最佳清洗窗口**。
    - **红色阴影区域**: **高风险窗口**。
    """)

elif 'data_loaded' not in st.session_state:
    st.info("👈 请点击左上角的 **“生成季度固定清洗计划”** 按钮开始分析。")

st.markdown("---")
st.caption("Quarterly Fixed Schedule Planner v13.0 | Smart State Management")
