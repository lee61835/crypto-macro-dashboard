import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 页面配置
st.set_page_config(page_title="Crypto 宏观流动性驾驶舱", layout="wide", page_icon="🌍")

st.title("🌍 Crypto 宏观流动性与风险预警系统")
st.markdown("""
> **数据来源**: Yahoo Finance (DXY, 美债, BTC) + FRED (通过代理逻辑模拟，确保云端稳定性)  
> **更新频率**: 每次刷新页面时自动获取最新数据  
> **无需安装**: 纯云端运行
""")

# 侧边栏
st.sidebar.header("控制面板")
refresh = st.sidebar.button("🔄 强制刷新数据")
st.sidebar.info("💡 提示：宏观数据（如美联储资产负债表）通常每周更新，市场数据实时变动。")

# 缓存数据获取函数 (提高加载速度)
@st.cache_data(ttl=3600)
def get_data():
    try:
        # 1. 获取市场数据 (Yahoo Finance)
        # DX-Y.NYB: 美元指数期货, ^TNX: 10年期美债收益率, BTC-USD: 比特币
        # 如果期货数据缺失，备用方案可以使用 UUP (美元ETF)
        tickers = ["DX-Y.NYB", "^TNX", "BTC-USD", "GLD"] 
        data = yf.download(tickers, period="2y", interval="1d", progress=False)['Close']
        
        # 重命名列
        data.columns = ["DXY", "Nominal_Yield", "BTC", "Gold"]
        
        # 数据清洗：删除全为空的行
        data = data.dropna(how='all')
        
        # 向前填充：解决不同市场休市时间不一致导致的数据空缺
        data = data.ffill()
        
        # 2. 模拟/计算实际利率 (Real Yields)
        # 注意：FRED API 在云端免费层有时受限，这里使用一种通用的估算方法：
        # 实际利率 ≈ 名义利率 (^TNX) - 通胀预期 (可以用 TIPS ETF 如 TIP 的价格变化率代理，或简化处理)
        # 为了演示稳定性，我们直接使用 名义利率 作为主要压力指标，因为短期两者高度相关
        # 如果有条件，可以加入 'TIP' ETF 数据来精确计算: Real = Nominal - Breakeven
        
        # 计算变化率
        data['DXY_Change'] = data['DXY'].pct_change()
        data['Yield_Change'] = data['Nominal_Yield'].pct_change()
        
        # 3. 构建压力分数
        # 逻辑：美元涨 (+1) + 利率涨 (+1) = 压力极大 (2)
        data['Score_DXY'] = data['DXY_Change'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        data['Score_Yield'] = data['Yield_Change'].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        
        data['Stress_Score'] = data['Score_DXY'] + data['Score_Yield']
        
        # 4. 计算相关性 (滚动 60)
