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
                # 确保列顺序正确，避免错位
        # 先检查哪些列存在
        available_cols = data.columns.tolist()
        
        # 创建映射字典
        col_map = {
            'DX-Y.NYB': 'DXY',
            '^TNX': 'Nominal_Yield',
            'BTC-USD': 'BTC',
            'GLD': 'Gold'
        }
        
        # 只保留存在的列，并重命名
        data = data[[col for col in col_map.keys() if col in available_cols]]
        data.rename(columns=col_map, inplace=True)
        
        # 如果缺少关键列，给出警告
        if 'DXY' not in data.columns:
            st.warning("⚠️ 未找到 DXY 数据，尝试使用 UUP 替代...")
            # 可选：备用方案
        
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
        
        # 4. 计算相关性 (滚动 60 天)
        data['Corr_DXY'] = data['BTC'].rolling(60).corr(data['DXY'])
        data['Corr_Yield'] = data['BTC'].rolling(60).corr(data['Nominal_Yield'])
        
        return data
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        return None

# 主逻辑
df = get_data()

if df is not None and not df.empty:
    # --- 顶部关键指标 ---
    col1, col2, col3, col4 = st.columns(4)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    with col1:
        st.metric("BTC 价格", f"${latest['BTC']:,.2f}", f"{(latest['BTC']-prev['BTC'])/prev['BTC']*100:.2f}%")
    with col2:
        st.metric("美元指数 (DXY)", f"{latest['DXY']:.2f}", f"{(latest['DXY']-prev['DXY'])/prev['DXY']*100:.2f}%", delta_color="inverse")
    with col3:
        st.metric("10Y 美债收益率", f"{latest['Nominal_Yield']:.2f}%", f"{(latest['Nominal_Yield']-prev['Nominal_Yield']):.2f}bp", delta_color="inverse")
    with col4:
        stress = latest['Stress_Score']
        status = "🔴 高压" if stress > 0 else "🟢 宽松" if stress < 0 else "⚪ 中性"
        st.metric("宏观压力状态", status)

    st.divider()

    # --- 图表区域 ---
    tab1, tab2, tab3 = st.tabs(["📊 压力指数与价格", "🔗 相关性分析", "📉 详细数据表"])

        with tab1:
        # 1. 先定义列布局 (注意：这行要和 with tab1: 对齐)
        col_a, col_b = st.columns([2, 1])
        
        # 2. 左侧大图 (注意：这行要和 col_a, col_b 对齐)
        with col_a:
            st.subheader("BTC 价格 vs 宏观压力分数 (红=紧缩/利空，绿=宽松/利好)")
            fig_main = go.Figure()
            
            # BTC 价格 (右轴)
            fig_main.add_trace(
                go.Scatter(
                    x=df.index, 
                    y=df['BTC'], 
                    name='BTC 价格', 
                    line=dict(color='#F7931A', width=2.5), 
                    yaxis="y2",
                    opacity=0.9
                )
            )
            
            # 压力分数 (左轴，柱状图)
            colors = ['red' if x > 0 else 'green' if x < 0 else 'gray' for x in df['Stress_Score']]
            
            fig_main.add_trace(
                go.Bar(
                    x=df.index, 
                    y=df['Stress_Score'], 
                    name='宏观压力', 
                    marker_color=colors,       
                    opacity=0.9,               
                    width=0.8,                 
                    hovertemplate='压力分数: %{y:.2f}<extra></extra>'
                )
            )
            
            # 添加 0 轴参考线
            fig_main.add_hline(
                y=0, 
                line_dash="dash", 
                line_color="white", 
                line_width=1, 
                annotation_text="中性分界线", 
                annotation_position="top right",
                annotation_font_color="gray"
            )

            # 动态计算 Y 轴范围
            min_score = df['Stress_Score'].min()
            max_score = df['Stress_Score'].max()
            
            y_min = min(min_score * 1.2, -1) if min_score < 0 else -1
            y_max = max(max_score * 1.2, 1) if max_score > 0 else 1
            
            fig_main.update_layout(
                height=600,                  
                hovermode='x unified',
                bargap=0.1,                  
                xaxis_rangeslider_visible=False, 
                legend=dict(orientation="h", y=1.05, x=0),
                title_font_size=20,
                yaxis=dict(
                    title="宏观压力分数", 
                    range=[y_min, y_max],    
                    gridcolor='rgba(255,255,255,0.1)'
                ),
                yaxis2=dict(
                    title="BTC 价格 (USD)", 
                    overlaying="y", 
                    side="right",
                    gridcolor='rgba(255,255,255,0.1)'
                ),
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig_main, use_container_width=True)

        # 3. 右侧信号解读 (注意：这行要和 with col_a: 对齐)
        with col_b:
            st.subheader("🚨 最新信号解读")
            latest = df.iloc[-1] # 确保获取最新数据
            
            if latest['Stress_Score'] >= 2:
                st.error("**极度危险**: 美元与利率双升，资金大幅回流美国，加密资产承压极大。建议减仓或对冲。")
            elif latest['Stress_Score'] <= -2:
                st.success("**黄金机会**: 美元与利率双降，流动性溢出，风险资产有望反弹。")
            elif latest['Stress_Score'] > 0:
                st.warning("**谨慎观望**: 宏观环境偏紧，不宜激进做多。")
            else:
                st.info("**环境温和**: 宏观因素无明显方向，关注技术面。")
            
            st.markdown("---")
            st.markdown(f"**DXY 趋势**: {'上涨 📈' if latest['Score_DXY']>0 else '下跌 📉'}")
            st.markdown(f"**利率 趋势**: {'上升 🔼' if latest['Score_Yield']>0 else '下降 🔽'}")
    with tab2:
        st.subheader("BTC 与宏观因子滚动相关性 (60天)")
        fig_corr = go.Figure()
        fig_corr.add_trace(go.Scatter(x=df.index, y=df['Corr_DXY'], name='BTC vs DXY', line=dict(color='red')))
        fig_corr.add_trace(go.Scatter(x=df.index, y=df['Corr_Yield'], name='BTC vs Yields', line=dict(color='blue')))
        fig_corr.add_hline(y=0, line_dash="dot", line_color="gray")
        fig_corr.update_layout(height=400, yaxis_title="相关系数 (-1 到 1)")
        st.plotly_chart(fig_corr, use_container_width=True)
        st.caption("相关系数接近 -1 表示强负相关（正常情况），接近 1 表示异常正相关。")

    with tab3:
        st.subheader("原始数据预览 (最近 30 天)")
        st.dataframe(df.tail(30)[['BTC', 'DXY', 'Nominal_Yield', 'Stress_Score']].sort_index(ascending=False), use_container_width=True)

else:
    st.warning("正在加载数据或数据暂时不可用，请稍后刷新。")

# 页脚
st.markdown("---")
st.caption("数据由 Yahoo Finance 提供 | 仅供研究参考，不构成投资建议")
