import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import math
import datetime

# ================= 页面配置 =================
st.set_page_config(
    page_title="光伏电站季度固定清洗计划与智能优选 (夜间清洗版)",
    page_icon="🌙",
    layout="wide"
)

# ================= ⭐ 行业常数与物理模型 ⭐
ROBOT_EFFICIENCY_MW_PER_DAY = 0.8
PANEL_POWER_W = 700
WATER_CONSUMPTION_PER_MW = 10.0
ENERGY_CONSUMPTION_PER_MW = 5.0
DUST_ACCUMULATION_RATE = 0.4
MAX_DUST_CAPACITY = 15.0
MAX_QUARTERLY_DAYS = 92 

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
st.sidebar.header("🌙 季度固定周期规划 (夜间清洗)")

selected_station = st.sidebar.selectbox("📍 选择目标电站", list(STATION_DB.keys()), index=0)

if 'last_params' not in st.session_state:
    st.session_state.last_params = {}

current_params = {
    'station': selected_station,
    'capacity': 0,
    'robots': 0,
    'dust_rate': 0,
    'manual_dates': {} 
}

config_valid = True

if selected_station != "请选择电站...":
    data = STATION_DB[selected_station]
    st.sidebar.subheader("⚙️ 电站规模与配置")
    capacity_mw = st.sidebar.number_input("⚡ 装机容量 (MW)", value=23.35, min_value=0.1, step=0.1)
    total_panels = int((capacity_mw * 1_000_000) / PANEL_POWER_W)
    st.sidebar.success(f"**🔢 太阳能板数量**: {total_panels:,} 块")
    
    robot_count = st.sidebar.number_input("🚜 可用机器人数量 (台)", value=5, min_value=1, step=1)
    daily_capacity = robot_count * ROBOT_EFFICIENCY_MW_PER_DAY
    days_to_clean_all = math.ceil(capacity_mw / daily_capacity) if daily_capacity > 0 else 999
    
    if days_to_clean_all > MAX_QUARTERLY_DAYS:
        config_valid = False
        st.sidebar.error(f"""
        ⚠️ **配置不可行！**
        当前工期：**{days_to_clean_all} 天** (超过季度上限 {MAX_QUARTERLY_DAYS} 天)
        **建议**: 增加机器人至 **{math.ceil(capacity_mw / (MAX_QUARTERLY_DAYS * ROBOT_EFFICIENCY_MW_PER_DAY))} 台** 以上。
        """)
    else:
        # 🌙 [优化] 移除关于清洗日发电折损的警告，因为夜间清洗不影响白天发电
        st.sidebar.info(f"💡 **清洗能力**: {daily_capacity:.1f} MW/天\n**单次全站工期**: **{days_to_clean_all} 天**")
        st.sidebar.success("**🌙 夜间清洗模式**: 清洗期间**无发电损失**，次日即可享受洁净增益。")

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
    
    current_params['capacity'] = capacity_mw
    current_params['robots'] = robot_count
    current_params['dust_rate'] = effective_dust_rate
    
    # ================= ✅ 手动清洗时间输入窗口 =================
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ 实际执行时间修正")
    st.sidebar.caption("留空则使用系统推荐，填入后强制覆盖。")
    
    manual_dates = {}
    today = datetime.date.today()
    
    for q in range(1, 5):
        with st.sidebar.expander(f"🗓️ Q{q} 实际执行时间", expanded=False):
            default_start = today + datetime.timedelta(days=(q-1)*90)
            default_end = default_start + datetime.timedelta(days=days_to_clean_all-1)
            
            m_start = st.date_input(f"Q{q} 开始日期", value=None, key=f"m_start_q{q}", help="手动输入实际开始清洗的日期")
            m_end = st.date_input(f"Q{q} 结束日期", value=None, key=f"m_end_q{q}", help="手动输入实际完成清洗的日期")
            
            if m_start:
                if not m_end:
                    m_end = m_start + datetime.timedelta(days=days_to_clean_all-1)
                    st.info(f"自动推算结束日期: {m_end}")
                
                if m_end < m_start:
                    st.error("结束日期不能早于开始日期！")
                    config_valid = False
                elif (m_end - m_start).days + 1 < days_to_clean_all:
                    st.warning(f"⚠️ 工期过短！理论需 {days_to_clean_all} 天，当前仅 {(m_end - m_start).days + 1} 天。可能导致清洗不彻底。")
                
                manual_dates[q] = {
                    "start": m_start,
                    "end": m_end,
                    "is_manual": True
                }
            else:
                manual_dates[q] = {"is_manual": False}
    
    current_params['manual_dates'] = manual_dates

else:
    st.stop()

params_changed = False
if st.session_state.last_params != current_params:
    params_changed = True
    st.session_state.last_params = current_params.copy()
    keys_to_clear = ['data_loaded', 'df_daily', 'rec_windows', 'filter_option']
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]

st.title(f"🌙 {selected_station} - 季度固定清洗计划 (夜间作业)")

if not config_valid:
    st.error(f"""
    ### 🛑 无法生成计划：配置或日期输入有误
    请返回左侧侧边栏调整参数或日期。
    """)
    st.stop()

st.markdown(f"**容量**: {capacity_mw} MW | **机器人**: {robot_count} 台 | **单次工期**: {days_to_clean_all} 天")

has_manual_input = any(v['is_manual'] for v in current_params['manual_dates'].values())
if has_manual_input:
    st.info("🔧 **混合模式激活**: 部分季度已手动指定清洗时间，系统将基于实际执行时间重新计算积灰与收益。")
else:
    st.info(f"""
    **🏢 公司合规策略 (夜间清洗版)**:
    1. **固定频次**: 严格执行 **每季度清洗一次**。
    2. **气象驱动**: 基于 **历史实测辐射与降雨数据** 预测未来一年收益。
    3. **零损耗作业**: 清洗在夜间进行，**白天发电无折损**，清洗完成后次日即刻提升效率。
    """)

# ================= ✅ 核心修改：获取包含辐射量的天气数据 =================
@st.cache_data(ttl=3600)
def get_real_historical_climate(lat, lon):
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily": ["precipitation_sum", "wind_speed_10m_max", "shortwave_radiation_sum"],
        "timezone": "America/Manaus"
    }
    try:
        with st.spinner("正在下载过去365天实测辐射与降雨数据..."):
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if 'daily' not in data or 'shortwave_radiation_sum' not in data['daily']:
                return None
            
            real_rain = data['daily']['precipitation_sum']
            real_wind = data['daily']['wind_speed_10m_max']
            real_radiation = data['daily']['shortwave_radiation_sum']
            
            if len(real_rain) < 300: return None
            
            future_start = datetime.datetime.now() + datetime.timedelta(days=1)
            future_dates = [(future_start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(len(real_rain))]
            
            return {
                "time": future_dates, 
                "precipitation_sum": real_rain, 
                "wind_speed_10m_max": real_wind,
                "shortwave_radiation_sum": real_radiation
            }
    except Exception as e:
        st.error(f"天气数据获取失败: {e}")
        return None

def analyze_quarterly_plan(weather_data, capacity, p_sell, p_elec, p_water, dust_rate, r_eff, clean_duration, manual_overrides):
    dates = weather_data['time']
    rain = weather_data['precipitation_sum']
    radiation = weather_data['shortwave_radiation_sum']
    
    HEAVY_RAIN_THRESHOLD = 5.0
    LIGHT_RAIN_THRESHOLD = 1.0
    
    # 计算单次清洗总成本 (水 + 电)
    total_cleaning_cost = (capacity * WATER_CONSUMPTION_PER_MW) * p_water + (capacity * ENERGY_CONSUMPTION_PER_MW) * p_elec
    
    date_objs = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates]
    step = len(dates) // 4
    q_ranges = [(0, step-1), (step, 2*step-1), (2*step, 3*step-1), (3*step, len(dates)-1)]
    
    recommended_windows = []
    chosen_days = set()
    
    # --- 第一步：预计算全年的自然积灰序列 (不含人工清洗) ---
    dust_series_natural = []
    current_dust = 0.0
    for i in range(len(dates)):
        r = rain[i]
        if r >= HEAVY_RAIN_THRESHOLD:
            current_dust = 0.0
        elif r >= LIGHT_RAIN_THRESHOLD:
            current_dust *= 0.5
        else:
            current_dust += dust_rate
        
        current_dust = min(current_dust, MAX_DUST_CAPACITY)
        dust_series_natural.append(current_dust)

    # --- 第二步：确定人工清洗窗口 (优先手动，其次自动) ---
    for q_idx in range(4):
        q_num = q_idx + 1
        q_start_range, q_end_range = q_ranges[q_idx]
        
        manual_info = manual_overrides.get(q_num, {})
        
        if manual_info.get('is_manual'):
            m_start_date = manual_info['start']
            m_end_date = manual_info['end']
            
            try:
                s_idx = dates.index(m_start_date.strftime("%Y-%m-%d"))
                e_idx = dates.index(m_end_date.strftime("%Y-%m-%d"))
                
                actual_duration = e_idx - s_idx + 1
                avg_dust = sum(dust_series_natural[k] for k in range(s_idx, e_idx+1)) / actual_duration
                
                recommended_windows.append({
                    'q': q_num, 
                    'start_idx': s_idx, 
                    'end_idx': e_idx,
                    'start_date': dates[s_idx], 
                    'end_date': dates[e_idx],
                    'avg_dust': avg_dust, 
                    'cost': total_cleaning_cost, 
                    'is_perfect': True, 
                    'is_manual': True
                })
                
                for k in range(s_idx, e_idx + 1): 
                    chosen_days.add(k)
                    
            except ValueError:
                st.warning(f"⚠️ Q{q_num} 的手动日期超出天气数据范围，该季度将回退到自动推荐。")
                pass
            continue 

        # 自动推荐逻辑
        best_start = -1
        best_score = -1
        best_avg_dust = 0
        is_perfect = False
        
        available_days = q_end_range - q_start_range + 1
        if available_days < clean_duration:
            continue
            
        for start in range(q_start_range, q_end_range - clean_duration + 1):
            end = start + clean_duration - 1
            is_safe = True
            max_rain = 0
            for k in range(start, end + 1):
                if rain[k] > HEAVY_RAIN_THRESHOLD:
                    is_safe = False
                    break
                max_rain = max(max_rain, rain[k])
            
            if is_safe:
                is_perfect = True
                avg_dust = sum(dust_series_natural[k] for k in range(start, end+1)) / clean_duration
                # 评分逻辑：积灰越高越需要洗，雨水越少越好
                score = avg_dust * 10 + (10 - max_rain)
                if score > best_score:
                    best_score = score
                    best_start = start
                    best_avg_dust = avg_dust
        
        if best_start == -1: 
            min_rain_sum = 99999
            for start in range(q_start_range, q_end_range - clean_duration + 1):
                r_sum = sum(rain[k] for k in range(start, start+clean_duration))
                if r_sum < min_rain_sum:
                    min_rain_sum = r_sum
                    best_start = start
            if best_start != -1:
                avg_dust = sum(dust_series_natural[k] for k in range(best_start, best_start+clean_duration))/clean_duration
            else:
                continue
        else:
            avg_dust = best_avg_dust
            
        if best_start != -1:
            for k in range(best_start, best_start + clean_duration): chosen_days.add(k)
            recommended_windows.append({
                'q': q_num, 'start_idx': best_start, 'end_idx': best_start + clean_duration - 1,
                'start_date': dates[best_start], 'end_date': dates[best_start + clean_duration - 1],
                'avg_dust': avg_dust, 'cost': total_cleaning_cost, 'is_perfect': is_perfect,
                'is_manual': False
            })

    # --- 第三步：生成最终积灰序列 (基于确定的窗口) ---
    final_dust_series = list(dust_series_natural)
    
    recommended_windows.sort(key=lambda x: x['start_idx'])

    for w in recommended_windows:
        clean_end_day = w['end_idx']
        
        # 🌙 [优化] 夜间清洗逻辑：
        # 清洗工作在第 clean_end_day 的晚上完成。
        # 因此，第 clean_end_day + 1 天 (如果存在) 的早晨，积灰度应直接归零 (或接近0)。
        # 注意：清洗期间 (start 到 end) 的白天，积灰度仍然按照自然累积计算，因为还没洗。
        
        next_day_idx = clean_end_day + 1
        if next_day_idx < len(final_dust_series):
            final_dust_series[next_day_idx] = 0.2 # 设置为一个很小的值，代表刚洗完
        
        # 重新计算清洗结束后的每一天
        for k in range(next_day_idx + 1, len(final_dust_series)):
            r = rain[k]
            prev_dust = final_dust_series[k-1]
            
            if r >= HEAVY_RAIN_THRESHOLD:
                final_dust_series[k] = 0.0
            elif r >= LIGHT_RAIN_THRESHOLD:
                final_dust_series[k] = prev_dust * 0.5
            else:
                final_dust_series[k] = prev_dust + dust_rate
            
            final_dust_series[k] = min(final_dust_series[k], MAX_DUST_CAPACITY)

    # --- 第四步：生成每日报表 ---
    daily_plans = []
    
    for i in range(len(dates)):
        date_obj = date_objs[i]
        weekday_cn = date_obj.strftime("%A")
        wk_map = {"Monday":"周一", "Tuesday":"周二", "Wednesday":"周三", "Thursday":"周四", "Friday":"周五", "Saturday":"周六", "Sunday":"周日"}
        
        is_rec = i in chosen_days
        q_info = next((w for w in recommended_windows if w['start_idx'] <= i <= w['end_idx']), None)
        
        daily_sun_hours = radiation[i] / 3.6
        theoretical_revenue = capacity * daily_sun_hours * 1000 * p_sell
        
        d_val = final_dust_series[i]
        efficiency_loss_factor = min(d_val / 100.0, 1.0)
        
        if is_rec and q_info:
            if q_info.get('is_manual'):
                status = f"🔧 Q{q_info['q']} 手动执行 (夜)"
                color = "blue"
            else:
                status = f"📅 Q{q_info['q']} 推荐 (夜)" if q_info['is_perfect'] else f"⚠️ Q{q_info['q']} 高风险 (夜)"
                color = "green" if q_info['is_perfect'] else "red"
            
            action = "Night Cleaning"
            
            # 🌙 [优化] 夜间清洗不扣除白天发电量！
            # actual_revenue = theoretical_revenue * (1 - efficiency_loss_factor) 
            # 这里的 logic 是：当天的积灰度 d_val 是白天累积的结果，晚上才洗。
            # 所以当天的发电损失是基于当天白天的积灰情况计算的，这是合理的。
            # 区别在于：不再额外乘以 derating_factor (之前代码里的 0.5~0.9 系数)。
            
            actual_revenue = theoretical_revenue * (1 - efficiency_loss_factor)
            
            # 成本只在开始那天计入，或者分摊，这里保持原逻辑：开始那天计入总成本
            daily_cost = total_cleaning_cost if i == q_info['start_idx'] else 0
            profit = actual_revenue - daily_cost
        else:
            if d_val < 3.0:
                status = "⚪ 积灰较少"
                color = "gray"
            elif 3.0 <= d_val < 7.0:
                status = "⚠️ 中度积灰"
                color = "orange"
            else:
                status = "🛑 重度积灰"
                color = "red"
            
            action = "Monitor"
            actual_revenue = theoretical_revenue * (1 - efficiency_loss_factor)
            daily_cost = 0
            profit = actual_revenue

        daily_plans.append({
            "日期": dates[i], "星期": wk_map.get(weekday_cn, ""), "季度": (i // step) + 1,
            "实测降雨 (mm)": round(rain[i], 1), 
            "日辐射量 (MJ/m²)": round(radiation[i], 1),
            "等效日照 (h)": round(daily_sun_hours, 1),
            "动态积灰度 (%)": round(d_val, 1),
            "操作建议": status, "状态颜色": color, "行动": action,
            "当日净现金流 ($)": round(profit, 1), "month_num": date_obj.month,
            "is_manual_clean": q_info.get('is_manual', False) if q_info else False
        })
        
    return pd.DataFrame(daily_plans), recommended_windows, HEAVY_RAIN_THRESHOLD

if st.button("🔍 生成/更新季度固定清洗计划", type="primary"):
    weather = get_real_historical_climate(LATITUDE, LONGITUDE)
    
    if weather:
        st.success(f"✅ **规划就绪**: 已加载实测辐射数据 (夜间清洗模式)。")
        
        # 🌙 [优化] 移除了 derating_factor 参数传递，因为不再需要
        df_daily, rec_windows, RAIN_THRESHOLD = analyze_quarterly_plan(
            weather, capacity_mw, sell_price, robot_elec_price, water_price, 
            effective_dust_rate, robot_eff, days_to_clean_all, 
            current_params['manual_dates']
        )
        
        st.session_state['df_daily'] = df_daily
        st.session_state['rec_windows'] = rec_windows
        st.session_state['data_loaded'] = True

if 'data_loaded' in st.session_state and st.session_state['data_loaded']:
    df_daily = st.session_state['df_daily']
    rec_windows = st.session_state['rec_windows']
    
    st.subheader("📊 年度季度清洗计划概览")
    cols = st.columns(4)
    total_cost = 0
    
    if len(rec_windows) < 4:
        st.warning(f"⚠️ 由于工期或日期范围限制，仅生成了 {len(rec_windows)} 个季度的计划。")
    
    for i, w in enumerate(rec_windows):
        total_cost += w['cost']
        if i < 4:
            date_range = f"{w['start_date'][5:]} ~ {w['end_date'][5:]}"
            detail = f"积灰:{w['avg_dust']:.1f}% | 成本:${w['cost']:,.0f}"
            
            is_manual = w.get('is_manual', False)
            
            with cols[i]:
                if is_manual:
                    st.metric(f"🔧 Q{i+1} (手动)", date_range, help=detail)
                    st.info(f"**已锁定执行 (夜)**\n{detail}", icon="🔒")
                elif w['is_perfect']:
                    st.metric(f"🗓️ Q{i+1}", date_range, help=detail)
                    st.success(f"**推荐窗口 (夜)**\n{detail}", icon="✅")
                else:
                    st.metric(f"🗓️ Q{i+1}", date_range, help=detail)
                    st.error(f"**高风险窗口 (夜)**\n{detail}", icon="⚠️")
    
    net_profit = df_daily['当日净现金流 ($)'].sum()
    st.info(f"**💰 年度预估总清洗成本**: ${total_cost:,.1f} | **年度预估净收益**: ${net_profit:,.1f}")
    
    st.markdown("<br>", unsafe_allow_html=True) 
    st.divider()
    
    st.subheader("📅 季度固定清洗执行计划表")
    
    with st.container():
        filter_options = ["显示所有日期", "仅显示 🌙 清洗期", "仅显示 ⚠️ 高风险清洗期"]
        
        if 'filter_option' not in st.session_state:
            st.session_state.filter_option = filter_options[0]
        
        selected_filter = st.radio(
            "🔍 视图过滤:", 
            filter_options, 
            horizontal=True,
            key='filter_option',
            label_visibility="collapsed"
        )
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    display_df = df_daily.copy()
    
    if selected_filter == "仅显示 🌙 清洗期":
        display_df = display_df[display_df['行动'] == "Night Cleaning"]
    elif selected_filter == "仅显示 ⚠️ 高风险清洗期":
        display_df = display_df[(display_df['行动'] == "Night Cleaning") & (display_df['状态颜色'] == 'red')]
    
    def color_code(val):
        if val is None: return ""
        val_str = str(val)
        if "手动" in val_str: return "color: white; font-weight: bold; background-color: #2563eb;" 
        if "推荐" in val_str: return "color: white; font-weight: bold; background-color: #16a34a;"
        if "高风险" in val_str: return "color: white; font-weight: bold; background-color: #dc2626;"
        if "较少" in val_str: return "color: gray; background-color: #f3f4f6;"
        if "中度" in val_str: return "color: white; font-weight: bold; background-color: #f97316;"
        if "重度" in val_str: return "color: white; font-weight: bold; background-color: #dc2626;"
        return ""
    
    def cash_flow_color(val):
        if val is None: return ""
        if val < 0: return "color: red; font-weight: bold;"
        else: return "color: green; font-weight: bold;"

    columns_to_show = [
        "日期", "星期", "季度", "实测降雨 (mm)", "日辐射量 (MJ/m²)", 
        "等效日照 (h)", "动态积灰度 (%)", "操作建议", "当日净现金流 ($)"
    ]
    
    st.dataframe(
        display_df[columns_to_show].style.applymap(color_code, subset=['操作建议'])
        .applymap(cash_flow_color, subset=['当日净现金流 ($)'])
        .format({
            "当日净现金流 ($)": "${:,.1f}", 
            "动态积灰度 (%)": "{:.1f}%",
            "日辐射量 (MJ/m²)": "{:.1f}",
            "等效日照 (h)": "{:.1f}",
            "实测降雨 (mm)": "{:.1f}"
        }), 
        use_container_width=True, 
        hide_index=True, 
        height=400
    )
    
    csv = display_df[columns_to_show].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下载季度计划 CSV", data=csv, file_name='quarterly_plan_night.csv', mime='text/csv')
    
    st.divider()
    
    st.subheader("📈 全年辐射、积灰趋势与发电收益")
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_daily['日期'], 
        y=df_daily['日辐射量 (MJ/m²)'],
        mode='lines', 
        name='日辐射量 (MJ/m²)',
        line=dict(color='orange', width=1, dash='dot'),
        opacity=0.6,
        yaxis='y1'
    ))

    fig.add_trace(go.Bar(
        x=df_daily['日期'], 
        y=df_daily['当日净现金流 ($)'],
        name='当日净现金流 ($)',
        marker_color=df_daily['当日净现金流 ($)'].apply(lambda x: 'green' if x > 0 else 'red'),
        opacity=0.8,
        yaxis='y2' 
    ))

    fig.add_trace(go.Scatter(
        x=df_daily['日期'], y=df_daily['动态积灰度 (%)'],
        mode='lines', name='动态积灰度 (%)',
        line=dict(color='purple', width=3),
        yaxis='y1' 
    ))
    
    for w in rec_windows:
        if w.get('is_manual'):
            color = 'blue'
            label = f"Q{w['q']} 手动 (夜)"
        elif w['is_perfect']:
            color = 'green'
            label = f"Q{w['q']} 推荐 (夜)"
        else:
            color = 'red'
            label = f"Q{w['q']} 高风险 (夜)"
            
        fig.add_vrect(
            x0=w['start_date'], 
            x1=w['end_date'],
            fillcolor=color, 
            opacity=0.15,
            line_width=0,
            annotation_text=label,
            annotation_position="top right"
        )
    
    fig.update_layout(
        height=600, 
        margin=dict(l=0, r=0, t=30, b=0),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        xaxis=dict(tickformat="%m-%d", tickangle=45, nticks=36),
        yaxis=dict(
            title="积灰度 (%) / 辐射 (MJ/m²)", 
            title_font=dict(color="purple", size=14),
            tickfont=dict(color="purple"),
            side='left'
        ),
        yaxis2=dict(
            title="当日净现金流 ($)", 
            title_font=dict(color="green", size=14),
            tickfont=dict(color="green"), 
            overlaying='y', 
            side='right'
        ),
        modebar_add=['v1hovermode', 'toggleSpikeLines'],
        modebar_remove=['toImage', 'pan2d', 'select2d', 'lasso2d', 'autoScale2d', 'resetScale2d', 'zoomIn2d', 'zoomOut2d', 'orbitRotation', 'tableRotation']
    )
        
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📚 数据来源与计算逻辑说明")
    
    with st.expander("点击查看详细数据来源与公式", expanded=False):
        st.markdown("""
        #### 1. 气象数据来源
        - **数据提供商**: [Open-Meteo Historical Archive API](https://open-meteo.com/)
        - **获取内容**: 过去 365 天的实测逐日数据（辐射量、降雨量、风速）。
        
        #### 2. 夜间清洗逻辑
        - **发电无损**: 清洗工作安排在日落后进行，**不占用白天发电时间**。
        - **积灰重置**: 清洗结束后的**次日清晨**，积灰度立即重置为接近 0%。
        - **收益计算**: 清洗期间的发电量仅受**当日积灰程度**影响，**不施加额外的工期折损系数**。
        
        #### 3. 积灰模型
        - **无雨时**: 积灰度每日增加 `日均积灰速率`
        - **小雨 (1.0mm-5.0mm)**: 积灰度减半
        - **大雨 (≥5.0mm)**: 积灰度清零
        - **最大积灰容量**: 15.0%
        
        #### 4. 计算公式
        - **等效日照 (h)** = 日辐射量 (MJ/m²) / 3.6
        - **发电量 (kWh)** = 装机容量 (MW) × 等效日照 (h) × 1000
        - **发电收益 (元)** = 发电量 (kWh) × 电价 (元/kWh)
        - **发电损失率** = 积灰度 (%) / 100.0
        - **当日净现金流** = (发电收益 × (1 - 发电损失率)) - 清洗成本
        """)
    
    st.caption("光伏电站季度固定清洗计划系统 v1.0")
    st.caption("数据来源: Open-Meteo Historical Archive API")
    st.caption("计算公式: 详见 '数据来源与计算逻辑说明' 部分")
    st.caption("系统开发: Jerrick_China_NP PSO")

elif 'data_loaded' not in st.session_state:
    if config_valid:
        st.info("👈 请点击左上角的 **“生成/更新季度固定清洗计划”** 按钮开始分析.")

# ================= 优化点: 在网页底部添加精确的引用信息 =================
st.markdown("---")
st.caption("光伏电站季度固定清洗计划与智能优选系统 v1.0")
st.caption("数据来源: Open-Meteo Historical Archive API (https://open-meteo.com/)")
st.caption("计算公式: ")
st.caption("- 等效日照 = 日辐射量 (MJ/m²) / 3.6")
st.caption("- 积灰度累积: 无雨时 + 日均积灰速率, 小雨时 × 0.5, 大雨时 = 0")
st.caption("- 当日净现金流 = (装机容量 × 等效日照 × 1000 × 电价) × (1 - 积灰度/100) - 清洗成本")
st.caption("© 2023-2024 Jerrick_China_NP PSO | 保留所有权利")
