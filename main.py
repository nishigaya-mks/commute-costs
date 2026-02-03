"""通勤費管理システム - ダッシュボード"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import pandas as pd

from utils import data_store, calculator, styles

st.set_page_config(
    page_title="通勤費管理",
    page_icon="🚗",
    layout="wide",
)

# モバイル対応CSS適用
styles.apply_mobile_styles()

st.title("🚗 通勤費管理")

# 現在の年月
today = date.today()
current_year = today.year
current_month = today.month

# --- 今月の収支サマリー ---
st.header(f"📊 {current_year}年{current_month}月の収支")

monthly_data = calculator.calculate_monthly_balance(current_year, current_month)

# 2x2グリッド（モバイルでも見やすい）
row1_col1, row1_col2 = st.columns(2)
row2_col1, row2_col2 = st.columns(2)

with row1_col1:
    st.metric(
        label="支給額",
        value=f"¥{monthly_data['allowance']:,}",
    )

with row1_col2:
    balance = monthly_data['balance']
    st.metric(
        label="差額",
        value=f"¥{balance:,}",
        delta=f"{'黒字' if balance >= 0 else '赤字'}",
        delta_color="normal" if balance >= 0 else "inverse",
    )

with row2_col1:
    st.metric(
        label="高速代",
        value=f"¥{monthly_data['etc_total']:,}",
    )

with row2_col2:
    st.metric(
        label="ガソリン代",
        value=f"¥{monthly_data['fuel_amount']:,}",
    )

# 通勤日数（参考情報）
st.caption(f"📅 通勤日数: {monthly_data['commute_days']}日（ETC利用日数）")

# 燃費情報
if monthly_data.get('fuel_efficiency'):
    st.caption(f"⛽ 今月の平均燃費: {monthly_data['fuel_efficiency']} km/L")

st.divider()

# --- 年間累計 ---
st.header(f"📈 {current_year}年 年間累計")

ytd_data = calculator.calculate_year_to_date_balance(current_year, current_month)

col1, col2 = st.columns(2)

with col1:
    ytd_balance = ytd_data['total_balance']
    color = "green" if ytd_balance >= 0 else "red"
    st.markdown(f"### 累計差額: <span style='color:{color}'>¥{ytd_balance:,}</span>", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    - 累計支給: ¥{ytd_data['total_allowance']:,}
    - 累計高速代: ¥{ytd_data['total_etc']:,}
    - 累計ガソリン代: ¥{ytd_data['total_fuel']:,}
    """)

# --- 月別推移グラフ ---
st.subheader("月別収支推移")

# グラフ設定
with st.expander("📐 グラフ設定", expanded=False):
    col_opt1, col_opt2, col_opt3 = st.columns(3)

    with col_opt1:
        chart_months = st.slider(
            "表示月数",
            min_value=3,
            max_value=36,
            value=12,
            step=1,
        )

    with col_opt2:
        y_min = st.number_input(
            "Y軸 最小値",
            value=-100000,
            step=10000,
            help="空欄で自動",
        )

    with col_opt3:
        y_max = st.number_input(
            "Y軸 最大値",
            value=100000,
            step=10000,
            help="空欄で自動",
        )

history = calculator.get_monthly_balance_history(chart_months)

if history and any(h['allowance'] > 0 or h['etc_total'] > 0 or h['fuel_amount'] > 0 for h in history):
    df = pd.DataFrame(history)

    # 収支推移グラフ
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='支給額',
        x=df['year_month'],
        y=df['allowance'],
        marker_color='#2ecc71',
    ))

    fig.add_trace(go.Bar(
        name='高速代',
        x=df['year_month'],
        y=[-v for v in df['etc_total']],
        marker_color='#e74c3c',
    ))

    fig.add_trace(go.Bar(
        name='ガソリン代',
        x=df['year_month'],
        y=[-v for v in df['fuel_amount']],
        marker_color='#f39c12',
    ))

    fig.add_trace(go.Scatter(
        name='差額',
        x=df['year_month'],
        y=df['balance'],
        mode='lines+markers',
        line=dict(color='#3498db', width=3),
        marker=dict(size=8),
    ))

    fig.update_layout(
        barmode='relative',
        xaxis_title='年月',
        yaxis_title='金額（円）',
        yaxis=dict(range=[y_min, y_max]),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("データがありません。ETC履歴の取り込みや給油記録の入力を行ってください。")

# --- 燃費推移 ---
st.subheader("⛽ 燃費推移")

fuel_trend = calculator.get_fuel_efficiency_trend(12)

if fuel_trend:
    df_fuel = pd.DataFrame(fuel_trend)

    fig_fuel = px.line(
        df_fuel,
        x='date',
        y='fuel_efficiency',
        markers=True,
        labels={'date': '日付', 'fuel_efficiency': '燃費 (km/L)'},
    )

    fig_fuel.update_layout(height=300)
    st.plotly_chart(fig_fuel, use_container_width=True)
else:
    st.info("給油記録がありません。")

# --- サイドバー ---
with st.sidebar:
    st.header("クイックアクション")

    if st.button("⛽ 給油を記録", use_container_width=True, type="primary"):
        st.switch_page("pages/1_⛽_給油記録.py")

    if st.button("📝 月次実績を入力", use_container_width=True):
        st.switch_page("pages/2_📝_月次実績.py")

    st.divider()

    st.caption("📁 ETC取込はPCから")
    st.caption("通勤費管理システム v1.0")
