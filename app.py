import streamlit as st
import pandas as pd
import ccxt
import time
from datetime import datetime

# --- 初始化交易所 (无需 API Key 即可获取公开行情) ---
binance = ccxt.binance({'options': {'defaultType': 'future'}}) # 币安合约
binance_spot = ccxt.binance({'options': {'defaultType': 'spot'}}) # 币安现货
coinbase = ccxt.coinbase() # Coinbase 现货

def fetch_hardcore_data():
    try:
        # 1. 抓取价格数据
        b_spot = binance_spot.fetch_ticker('BTC/USDT')
        b_future = binance.fetch_ticker('BTC/USDT')
        cb_spot = coinbase.fetch_ticker('BTC/USD')
        
        # 2. 抓取持仓量 (Open Interest)
        # 使用币安 fapi 接口获取实时持仓
        oi_resp = binance.fapiPublicGetOpenInterest({'symbol': 'BTCUSDT'})
        oi_value = float(oi_resp['openInterest'])
        
        # 3. 抓取 24h 成交量
        vol_spot = float(b_spot['quoteVolume'])
        vol_future = float(b_future['quoteVolume'])
        
        return {
            "s_price": b_spot['close'],
            "f_price": b_future['close'],
            "cb_price": cb_spot['close'],
            "oi": oi_value,
            "s_vol": vol_spot,
            "f_vol": vol_future,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        st.error(f"数据抓取失败: {e}")
        return None

# --- Streamlit 页面配置 ---
st.set_page_config(page_title="BTC 硬核监控站", layout="wide")
st.title("🛡️ BTC 全网资金压力实时仪表盘")
st.caption("数据源: Binance API & Coinbase API | 每 10 秒自动刷新")

# 侧边栏设置
refresh_rate = st.sidebar.slider("刷新频率 (秒)", 5, 60, 10)

# --- 核心逻辑运行 ---
data = fetch_hardcore_data()

if data:
    # 指标 1: 基差 (Basis)
    basis_pct = (data['f_price'] - data['s_price']) / data['s_price'] * 100
    
    # 指标 2: 赌场系数 (Spot/Future Ratio)
    casino_ratio = data['f_vol'] / data['s_vol']
    
    # 指标 3: Coinbase 溢价 (美资动力)
    cb_premium = (data['cb_price'] - data['s_price']) / data['s_price'] * 100

    # --- UI 展示 ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("合约价格", f"${data['f_price']:,}")
        st.metric("现货价格", f"${data['s_price']:,}")
        
    with col2:
        st.metric("基差率 (Basis %)", f"{basis_pct:.4f}%", 
                  delta="多头过热" if basis_pct > 0.1 else "正常", delta_color="inverse")
        st.caption("物理意义: 合约比现货贵多少")

    with col3:
        st.metric("赌场系数 (合约/现货)", f"{casino_ratio:.1f}x",
                  delta="风险极高" if casino_ratio > 15 else "安全", delta_color="inverse")
        st.caption("物理意义: 杠杆资金是现货的几倍")

    with col4:
        st.metric("CB 溢价 (美资)", f"{cb_premium:.4f}%",
                  delta="机构买入" if cb_premium > 0 else "机构抛售")
        st.caption("物理意义: 华尔街/ETF 的入场意愿")

    st.divider()

    # --- 风险诊断 ---
    st.subheader("⚠️ 实时风险诊断报告")
    c_left, c_right = st.columns(2)
    
    with c_left:
        if casino_ratio > 20:
            st.error(f"【高危】当前赌场系数为 {casino_ratio:.1f}。杠杆资金严重过载，极易发生双边爆仓！")
        elif basis_pct > 0.15:
            st.warning("【警报】基差过大。套利资金可能随时入场抹平价差，注意多头踩踏。")
        else:
            st.success("市场资金结构目前相对健康。")
            
    with c_right:
        if cb_premium < -0.05:
            st.error("【趋势风险】Coinbase 出现显著折价。美资机构正在撤退，即便价格在涨也是‘假突破’。")
        elif cb_premium > 0.05:
            st.success("【动力强劲】美资溢价中。这一轮上涨由机构现货买盘驱动，支撑力强。")

    # 自动刷新逻辑
    time.sleep(refresh_rate)
    st.rerun()
