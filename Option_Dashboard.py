import streamlit as st
import pandas as pd
import numpy as np
import akshare as ak
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(
    page_title="期权Greeks Cash分析",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 标题和说明
st.title("📊 期权Greeks Cash分析仪表板")
st.markdown("""
分析当前持仓期权的Greeks Cash值，并展示Greeks随标的价格变化的曲线。
""")

# ETF合约乘数配置
CONTRACT_MULTIPLIER = 10000  # ETF期权合约乘数
DAYS_PER_YEAR = 365  # 每年自然日数量（用于Theta日化计算）

# ETF标的代码映射（支持上交所和深交所全部ETF期权品种）
ETF_UNDERLYING = {
    # 上交所
    "50ETF": "sh510050",           # 上证50ETF
    "300ETF": "sh510300",          # 沪深300ETF (华泰柏瑞)
    "500ETF": "sh510500",          # 中证500ETF (南方)
    "科创50": "sh588000",          # 科创50ETF (华夏)
    "科创板50": "sh588080",        # 科创板50ETF (易方达)
    # 深交所
    "创业板ETF": "sz159915",       # 创业板ETF
    "深100ETF": "sz159901",        # 深证100ETF
    "中证500ETF": "sz159922",      # 中证500ETF (嘉实)
    "沪深300ETF": "sz159919",      # 沪深300ETF (嘉实)
}


@st.cache_data(ttl=60)  # 缓存60秒
def get_option_risk_data():
    """获取期权风险分析数据"""
    try:
        df = ak.option_risk_analysis_em()
        return df
    except Exception as e:
        st.error(f"获取期权数据失败: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60)
def get_etf_price(symbol):
    """获取ETF实时价格"""
    try:
        spot_price_df = ak.option_sse_underlying_spot_price_sina(symbol=symbol)
        current_price = float(spot_price_df.loc[spot_price_df['字段'] == '最近成交价', '值'].iloc[0])
        return current_price
    except Exception as e:
        return None


def identify_etf_type(option_name):
    """根据期权名称识别ETF类型"""
    # 按匹配优先级排序（更具体的先匹配）
    # 科创板50 vs 科创50 需要区分
    if "科创板50" in option_name or "科创板ETF" in option_name:
        return "科创板50", "sh588080"
    elif "科创50" in option_name:
        return "科创50", "sh588000"
    # 区分上交所和深交所的300ETF和500ETF
    elif "嘉实沪深300" in option_name or "深300ETF" in option_name:
        return "沪深300ETF", "sz159919"
    elif "300ETF" in option_name or "沪深300" in option_name:
        return "300ETF", "sh510300"
    elif "嘉实中证500" in option_name or "深500ETF" in option_name:
        return "中证500ETF", "sz159922"
    elif "500ETF" in option_name or "中证500" in option_name:
        return "500ETF", "sh510500"
    elif "50ETF" in option_name and "科创" not in option_name:
        return "50ETF", "sh510050"
    elif "创业板" in option_name:
        return "创业板ETF", "sz159915"
    elif "深100" in option_name:
        return "深100ETF", "sz159901"
    else:
        return "未知", None


def parse_option_name(option_name):
    """
    解析期权名称，提取ETF类型、合约月份、行权价、期权类型
    例如: "300ETF购1月4000" -> ("300ETF", "1月", 4000, "购")
          "科创50沽2月1500" -> ("科创50", "2月", 1500, "沽")
    """
    import re
    
    # 识别ETF类型（按匹配优先级排序，更具体的先匹配）
    etf_patterns = [
        ("科创板50", r"科创板50|科创板ETF"),        # 易方达科创板50
        ("科创50", r"科创50"),                      # 华夏科创50
        ("沪深300ETF", r"嘉实沪深300|深300ETF"),    # 深交所300ETF
        ("300ETF", r"300ETF|沪深300"),              # 上交所300ETF
        ("中证500ETF", r"嘉实中证500|深500ETF"),    # 深交所500ETF
        ("500ETF", r"500ETF|中证500"),              # 上交所500ETF
        ("50ETF", r"(?<!300)(?<!500)(?<!科创)(?<!科创板)50ETF"),  # 上证50ETF
        ("创业板ETF", r"创业板"),                   # 创业板ETF
        ("深100ETF", r"深100"),                     # 深证100ETF
    ]
    
    etf_type = "未知"
    for name, pattern in etf_patterns:
        if re.search(pattern, option_name):
            etf_type = name
            break
    
    # 识别期权类型（购/沽）
    if "购" in option_name:
        option_type = "购"
    elif "沽" in option_name:
        option_type = "沽"
    else:
        option_type = "未知"
    
    # 提取合约月份 (例如: 1月, 2月, 12月)
    month_match = re.search(r'[购沽](\d{1,2})月', option_name)
    if month_match:
        contract_month = f"{month_match.group(1)}月"
    else:
        contract_month = "未知"
    
    # 提取行权价 (月份后面的数字)
    strike_match = re.search(r'月(\d+)', option_name)
    if strike_match:
        strike_price = int(strike_match.group(1))
    else:
        strike_price = 0
    
    return etf_type, contract_month, strike_price, option_type


def add_parsed_columns(df):
    """为期权数据添加解析后的列"""
    parsed_data = df['期权名称'].apply(parse_option_name)
    df['ETF标的'] = parsed_data.apply(lambda x: x[0])
    df['合约月份'] = parsed_data.apply(lambda x: x[1])
    df['行权价'] = parsed_data.apply(lambda x: x[2])
    df['期权类型'] = parsed_data.apply(lambda x: x[3])
    return df


def calculate_greeks_cash(delta, gamma, vega, theta, underlying_price, position_size, is_short=False):
    """
    计算Greeks Cash值
    
    参数:
    - delta, gamma, vega, theta: 原始Greeks值
    - underlying_price: 标的价格
    - position_size: 持仓张数
    - is_short: 是否为义务仓(卖出)
    
    返回:
    - Greeks Cash字典
    """
    # 义务仓需要取反
    multiplier = -1 if is_short else 1
    
    # Delta Cash = Delta × 合约乘数 × 标的价格 × 持仓张数
    delta_cash = delta * CONTRACT_MULTIPLIER * underlying_price * position_size * multiplier
    
    # Gamma Cash = Gamma × 合约乘数 × 标的价格^2 × 0.01 × 持仓张数 (每1%变动)
    gamma_cash = gamma * CONTRACT_MULTIPLIER * (underlying_price ** 2) * 0.01 * position_size * multiplier
    
    # Vega Cash = Vega × 合约乘数 × 持仓张数 (每1%波动率变动)
    vega_cash = vega * CONTRACT_MULTIPLIER * position_size * multiplier
    
    # Theta Cash = Theta × 合约乘数 × 持仓张数 / 365 (每日，Theta原始单位为年)
    theta_cash = theta * CONTRACT_MULTIPLIER * position_size * multiplier / DAYS_PER_YEAR
    
    return {
        'Delta Cash': delta_cash,
        'Gamma Cash': gamma_cash,
        'Vega Cash': vega_cash,
        'Theta Cash': theta_cash
    }


def simulate_greeks_vs_price(delta, gamma, underlying_price, price_range_pct=0.1, steps=50):
    """
    模拟Greeks随标的价格变化的曲线
    
    使用Delta和Gamma的关系来估算不同价格下的Delta值:
    Delta_new ≈ Delta_old + Gamma × (S_new - S_old)
    
    参数:
    - delta: 当前Delta值
    - gamma: 当前Gamma值
    - underlying_price: 当前标的价格
    - price_range_pct: 价格变动范围百分比
    - steps: 模拟步数
    
    返回:
    - prices: 价格数组
    - deltas: 对应的Delta数组
    """
    # 生成价格范围
    price_min = underlying_price * (1 - price_range_pct)
    price_max = underlying_price * (1 + price_range_pct)
    prices = np.linspace(price_min, price_max, steps)
    
    # 使用Gamma估算不同价格下的Delta
    price_changes = prices - underlying_price
    deltas = delta + gamma * price_changes
    
    # 限制Delta在合理范围内 (-1 to 1)
    deltas = np.clip(deltas, -1, 1)
    
    return prices, deltas


# 初始化session state
if 'positions' not in st.session_state:
    st.session_state.positions = []

# 侧边栏 - 添加持仓
st.sidebar.header("📋 添加持仓")

# 刷新数据按钮
if st.sidebar.button("🔄 刷新期权数据"):
    st.cache_data.clear()
    st.rerun()

# 获取期权数据
with st.spinner("正在加载期权数据..."):
    option_data = get_option_risk_data()

if option_data.empty:
    st.error("无法获取期权数据，请稍后重试")
    st.stop()

# 解析期权名称，添加分类列
option_data = add_parsed_columns(option_data)

st.sidebar.success(f"已加载 {len(option_data)} 个期权合约")

# ============ 级联下拉框选择期权 ============

# 1. 选择ETF标的
etf_types = sorted(option_data['ETF标的'].unique().tolist())
# 过滤掉"未知"
etf_types = [e for e in etf_types if e != "未知"]
selected_etf = st.sidebar.selectbox(
    "① 选择ETF标的",
    etf_types,
    help="选择期权对应的ETF标的"
)

# 根据ETF标的过滤数据
filtered_by_etf = option_data[option_data['ETF标的'] == selected_etf]

# 2. 选择合约月份
contract_months = sorted(filtered_by_etf['合约月份'].unique().tolist(), 
                         key=lambda x: int(x.replace('月', '')) if x != '未知' else 99)
contract_months = [m for m in contract_months if m != "未知"]
selected_month = st.sidebar.selectbox(
    "② 选择合约月份",
    contract_months,
    help="选择期权的到期月份"
)

# 根据月份过滤数据
filtered_by_month = filtered_by_etf[filtered_by_etf['合约月份'] == selected_month]

# 3. 选择行权价
strike_prices = sorted(filtered_by_month['行权价'].unique().tolist())
strike_prices = [s for s in strike_prices if s > 0]
selected_strike = st.sidebar.selectbox(
    "③ 选择行权价",
    strike_prices,
    help="选择期权的行权价格"
)

# 根据行权价过滤数据
filtered_by_strike = filtered_by_month[filtered_by_month['行权价'] == selected_strike]

# 4. 选择购权/沽权
option_types = filtered_by_strike['期权类型'].unique().tolist()
option_types = [t for t in option_types if t != "未知"]
selected_option_type = st.sidebar.selectbox(
    "④ 选择购权/沽权",
    option_types,
    format_func=lambda x: "认购 (Call)" if x == "购" else "认沽 (Put)",
    help="购权(Call)看涨，沽权(Put)看跌"
)

# 最终筛选出的期权
final_filtered = filtered_by_strike[filtered_by_strike['期权类型'] == selected_option_type]

if len(final_filtered) > 0:
    selected_option = final_filtered.iloc[0]['期权名称']
    # 显示选中的期权信息
    st.sidebar.info(f"📌 已选择: **{selected_option}**")
else:
    selected_option = None
    st.sidebar.warning("未找到匹配的期权合约")

# 仓位类型
st.sidebar.markdown("---")
position_type = st.sidebar.radio(
    "⑤ 仓位类型",
    ["权利仓 (买入)", "义务仓 (卖出)"],
    help="权利仓：买入期权，Greeks保持原值；义务仓：卖出期权，Greeks取反"
)

# 持仓张数
position_size = st.sidebar.number_input(
    "⑥ 持仓张数",
    min_value=1,
    max_value=10000,
    value=1,
    step=1,
    help="输入持仓的合约张数"
)

# 显示选中期权的Greeks预览
if selected_option and len(final_filtered) > 0:
    option_info_preview = final_filtered.iloc[0]
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📊 Greeks预览:**")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.sidebar.metric("Delta", f"{option_info_preview['Delta']:.4f}")
        st.sidebar.metric("Vega", f"{option_info_preview['Vega']:.4f}")
    with col2:
        st.sidebar.metric("Gamma", f"{option_info_preview['Gamma']:.4f}")
        st.sidebar.metric("Theta", f"{option_info_preview['Theta']:.4f}")
    st.sidebar.caption(f"最新价: {option_info_preview['最新价']:.4f} | 到期日: {option_info_preview['到期日']}")

# 添加持仓按钮
st.sidebar.markdown("---")
add_button_disabled = selected_option is None
if st.sidebar.button("➕ 添加到持仓", disabled=add_button_disabled):
    if selected_option:
        # 获取选中期权的详细信息
        option_info = option_data[option_data['期权名称'] == selected_option].iloc[0]
        
        # 识别ETF类型
        etf_type, etf_symbol = identify_etf_type(selected_option)
        
        # 获取标的价格
        underlying_price = None
        if etf_symbol:
            underlying_price = get_etf_price(etf_symbol)
        
        if underlying_price is None:
            # 使用期权价格估算标的价格（简单估算）
            underlying_price = option_info['最新价'] * 100  # 粗略估计
        
        is_short = "义务仓" in position_type
        
        new_position = {
            'id': len(st.session_state.positions),
            '期权代码': option_info['期权代码'],
            '期权名称': selected_option,
            'ETF类型': etf_type,
            'ETF代码': etf_symbol,
            '标的价格': underlying_price,
            '最新价': option_info['最新价'],
            '仓位类型': '义务仓' if is_short else '权利仓',
            '持仓张数': position_size,
            'Delta': option_info['Delta'],
            'Gamma': option_info['Gamma'],
            'Vega': option_info['Vega'],
            'Theta': option_info['Theta'],
            '到期日': option_info['到期日'],
            'is_short': is_short
        }
        
        st.session_state.positions.append(new_position)
        st.sidebar.success(f"已添加: {selected_option}")
        st.rerun()

# 清空持仓按钮
if st.sidebar.button("🗑️ 清空所有持仓"):
    st.session_state.positions = []
    st.rerun()

# 主界面
if not st.session_state.positions:
    st.info("👆 请在左侧添加期权持仓")
    
    # 显示期权数据预览
    st.subheader(f"📋 可用期权合约预览 (共 {len(option_data)} 条)")
    display_cols = ['期权代码', '期权名称', '最新价', '涨跌幅', 'Delta', 'Gamma', 'Vega', 'Theta', '到期日']
    st.dataframe(
        option_data[display_cols],
        use_container_width=True,
        hide_index=True,
        height=500  # 设置固定高度，支持滚动浏览全部数据
    )
else:
    # 显示持仓列表
    st.subheader("📊 当前持仓")
    
    # 创建持仓DataFrame用于编辑
    positions_df = pd.DataFrame(st.session_state.positions)
    
    # 创建可编辑的持仓表格
    st.markdown("#### 📋 持仓明细 (可编辑)")
    st.caption("💡 直接修改「持仓张数」列的数值，或勾选「删除」列后点击下方按钮删除")
    
    # 准备显示用的DataFrame，添加删除选择列
    edit_df = positions_df[['期权名称', 'ETF类型', '仓位类型', '持仓张数', '最新价', 'Delta', 'Gamma', 'Vega', 'Theta', '到期日']].copy()
    edit_df.insert(0, '删除', False)  # 在最前面添加删除复选框列
    
    # 使用data_editor创建可编辑表格
    edited_df = st.data_editor(
        edit_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "删除": st.column_config.CheckboxColumn(
                "🗑️",
                help="勾选要删除的持仓",
                default=False,
                width="small"
            ),
            "持仓张数": st.column_config.NumberColumn(
                "持仓张数",
                help="修改持仓张数",
                min_value=1,
                max_value=10000,
                step=1,
                width="small"
            ),
            "期权名称": st.column_config.TextColumn(
                "期权名称",
                disabled=True,
                width="medium"
            ),
            "ETF类型": st.column_config.TextColumn(
                "ETF类型",
                disabled=True,
                width="small"
            ),
            "仓位类型": st.column_config.TextColumn(
                "仓位类型",
                disabled=True,
                width="small"
            ),
            "最新价": st.column_config.NumberColumn(
                "最新价",
                disabled=True,
                format="%.4f"
            ),
            "Delta": st.column_config.NumberColumn(
                "Delta",
                disabled=True,
                format="%.4f"
            ),
            "Gamma": st.column_config.NumberColumn(
                "Gamma",
                disabled=True,
                format="%.4f"
            ),
            "Vega": st.column_config.NumberColumn(
                "Vega",
                disabled=True,
                format="%.4f"
            ),
            "Theta": st.column_config.NumberColumn(
                "Theta",
                disabled=True,
                format="%.4f"
            ),
            "到期日": st.column_config.TextColumn(
                "到期日",
                disabled=True,
                width="small"
            ),
        },
        key="positions_editor"
    )
    
    # 处理删除和更新操作
    col_del, col_update = st.columns(2)
    
    with col_del:
        # 删除选中的持仓
        rows_to_delete = edited_df[edited_df['删除'] == True].index.tolist()
        if rows_to_delete:
            if st.button(f"🗑️ 删除选中的 {len(rows_to_delete)} 条持仓", type="primary"):
                # 从后往前删除，避免索引变化问题
                for idx in sorted(rows_to_delete, reverse=True):
                    st.session_state.positions.pop(idx)
                st.rerun()
    
    with col_update:
        # 检查持仓张数是否有变化
        positions_changed = False
        for i, row in edited_df.iterrows():
            if row['持仓张数'] != st.session_state.positions[i]['持仓张数']:
                positions_changed = True
                break
        
        if positions_changed:
            if st.button("💾 保存张数修改", type="primary"):
                for i, row in edited_df.iterrows():
                    st.session_state.positions[i]['持仓张数'] = int(row['持仓张数'])
                st.success("持仓张数已更新！")
                st.rerun()
    
    # 重新计算Greeks Cash（使用更新后的数据）
    greeks_cash_list = []
    
    for i, pos in enumerate(st.session_state.positions):
        # 使用编辑后的持仓张数
        current_position_size = int(edited_df.iloc[i]['持仓张数']) if i < len(edited_df) else pos['持仓张数']
        
        underlying_price = pos['标的价格']
        if underlying_price is None or underlying_price <= 0:
            underlying_price = pos['最新价'] * 100
        
        greeks_cash = calculate_greeks_cash(
            delta=pos['Delta'],
            gamma=pos['Gamma'],
            vega=pos['Vega'],
            theta=pos['Theta'],
            underlying_price=underlying_price,
            position_size=current_position_size,
            is_short=pos['is_short']
        )
        greeks_cash['期权名称'] = pos['期权名称']
        greeks_cash['仓位类型'] = pos['仓位类型']
        greeks_cash['持仓张数'] = current_position_size
        greeks_cash['标的价格'] = underlying_price
        greeks_cash_list.append(greeks_cash)
    
    greeks_cash_df = pd.DataFrame(greeks_cash_list)
    
    st.markdown("")  # 换行
    
    st.markdown("#### 💰 Greeks Cash (单位: 元)")
    # 格式化显示
    display_greeks = greeks_cash_df[['期权名称', '仓位类型', '持仓张数', 'Delta Cash', 'Gamma Cash', 'Vega Cash', 'Theta Cash']].copy()
    for col in ['Delta Cash', 'Gamma Cash', 'Vega Cash', 'Theta Cash']:
        display_greeks[col] = display_greeks[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(display_greeks, use_container_width=True, hide_index=True)
    
    # 汇总Greeks Cash
    st.markdown("---")
    st.subheader("📈 组合Greeks Cash汇总")
    
    total_delta_cash = greeks_cash_df['Delta Cash'].sum()
    total_gamma_cash = greeks_cash_df['Gamma Cash'].sum()
    total_vega_cash = greeks_cash_df['Vega Cash'].sum()
    total_theta_cash = greeks_cash_df['Theta Cash'].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Delta Cash",
            f"¥{total_delta_cash:,.2f}",
            help="标的价格变动1元，组合价值变动量"
        )
    
    with col2:
        st.metric(
            "Gamma Cash",
            f"¥{total_gamma_cash:,.2f}",
            help="标的价格变动1%时，Delta Cash的变动量"
        )
    
    with col3:
        st.metric(
            "Vega Cash",
            f"¥{total_vega_cash:,.2f}",
            help="隐含波动率变动1%时，组合价值变动量"
        )
    
    with col4:
        st.metric(
            "Theta Cash",
            f"¥{total_theta_cash:,.2f}",
            help="每日时间价值损耗（年化Theta÷365）"
        )
    
    # 绘制Greeks随价格变化的曲线图
    st.markdown("---")
    st.subheader("📉 Greeks随标的价格变化曲线")
    
    # 价格变动范围设置
    price_range = st.slider(
        "价格变动范围 (%)",
        min_value=5,
        max_value=30,
        value=10,
        step=1,
        help="设置模拟价格变动的范围"
    )
    
    # 为每个持仓创建曲线图
    for pos in st.session_state.positions:
        underlying_price = pos['标的价格']
        if underlying_price is None or underlying_price <= 0:
            underlying_price = pos['最新价'] * 100
        
        # 模拟Delta随价格变化
        prices, deltas = simulate_greeks_vs_price(
            delta=pos['Delta'],
            gamma=pos['Gamma'],
            underlying_price=underlying_price,
            price_range_pct=price_range / 100,
            steps=100
        )
        
        # 考虑仓位方向
        multiplier = -1 if pos['is_short'] else 1
        adjusted_deltas = deltas * multiplier
        
        # 计算Delta Cash曲线
        delta_cash_curve = adjusted_deltas * CONTRACT_MULTIPLIER * prices * pos['持仓张数']
        
        # 创建子图
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(f"Delta曲线", f"Delta Cash曲线"),
            horizontal_spacing=0.1
        )
        
        # Delta曲线
        fig.add_trace(
            go.Scatter(
                x=prices,
                y=adjusted_deltas,
                mode='lines',
                name='Delta',
                line=dict(color='blue', width=2)
            ),
            row=1, col=1
        )
        
        # 标记当前价格点
        current_delta = pos['Delta'] * multiplier
        fig.add_trace(
            go.Scatter(
                x=[underlying_price],
                y=[current_delta],
                mode='markers',
                name='当前位置',
                marker=dict(color='red', size=12, symbol='star')
            ),
            row=1, col=1
        )
        
        # Delta Cash曲线
        fig.add_trace(
            go.Scatter(
                x=prices,
                y=delta_cash_curve,
                mode='lines',
                name='Delta Cash',
                line=dict(color='green', width=2)
            ),
            row=1, col=2
        )
        
        # 标记当前Delta Cash点
        current_delta_cash = current_delta * CONTRACT_MULTIPLIER * underlying_price * pos['持仓张数']
        fig.add_trace(
            go.Scatter(
                x=[underlying_price],
                y=[current_delta_cash],
                mode='markers',
                name='当前位置',
                marker=dict(color='red', size=12, symbol='star'),
                showlegend=False
            ),
            row=1, col=2
        )
        
        # 更新布局
        fig.update_layout(
            title=f"{pos['期权名称']} ({pos['仓位类型']}, {pos['持仓张数']}张)",
            height=400,
            showlegend=True
        )
        
        fig.update_xaxes(title_text="标的价格", row=1, col=1)
        fig.update_xaxes(title_text="标的价格", row=1, col=2)
        fig.update_yaxes(title_text="Delta", row=1, col=1)
        fig.update_yaxes(title_text="Delta Cash (元)", row=1, col=2)
        
        st.plotly_chart(fig, use_container_width=True)
    
    # 组合Greeks Cash曲线
    st.markdown("---")
    st.subheader("📊 组合Greeks Cash随标的价格变化")
    
    # 获取所有持仓的标的价格范围
    all_underlying_prices = [pos['标的价格'] if pos['标的价格'] and pos['标的价格'] > 0 else pos['最新价'] * 100 
                            for pos in st.session_state.positions]
    avg_underlying_price = np.mean(all_underlying_prices)
    
    # 生成价格范围
    price_min = avg_underlying_price * (1 - price_range / 100)
    price_max = avg_underlying_price * (1 + price_range / 100)
    prices = np.linspace(price_min, price_max, 100)
    
    # 初始化组合Greeks Cash曲线
    total_delta_cash_curve = np.zeros_like(prices)
    total_gamma_cash_curve = np.zeros_like(prices)
    total_vega_cash_curve = np.zeros_like(prices)
    total_theta_cash_curve = np.zeros_like(prices)
    
    for pos in st.session_state.positions:
        underlying_price = pos['标的价格']
        if underlying_price is None or underlying_price <= 0:
            underlying_price = pos['最新价'] * 100
        
        # 模拟Delta随价格变化
        _, deltas = simulate_greeks_vs_price(
            delta=pos['Delta'],
            gamma=pos['Gamma'],
            underlying_price=underlying_price,
            price_range_pct=price_range / 100,
            steps=100
        )
        
        multiplier = -1 if pos['is_short'] else 1
        adjusted_deltas = deltas * multiplier
        
        # Delta Cash曲线
        delta_cash_curve = adjusted_deltas * CONTRACT_MULTIPLIER * prices * pos['持仓张数']
        total_delta_cash_curve += delta_cash_curve
        
        # Gamma Cash曲线 (Gamma随价格变化较小，这里假设Gamma不变)
        gamma_cash_curve = pos['Gamma'] * multiplier * CONTRACT_MULTIPLIER * (prices ** 2) * 0.01 * pos['持仓张数']
        total_gamma_cash_curve += gamma_cash_curve
        
        # Vega Cash曲线 (Vega随价格变化，ATM时最大)
        # 简化处理：假设Vega与Delta的关系，平值附近Vega最大
        vega_base = pos['Vega'] * multiplier * CONTRACT_MULTIPLIER * pos['持仓张数']
        total_vega_cash_curve += np.full_like(prices, vega_base)
        
        # Theta Cash曲线 (Theta随价格变化，ATM时Theta绝对值最大，除以365转为每日)
        theta_base = pos['Theta'] * multiplier * CONTRACT_MULTIPLIER * pos['持仓张数'] / DAYS_PER_YEAR
        total_theta_cash_curve += np.full_like(prices, theta_base)
    
    # 创建2x2子图
    fig_combined = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Delta Cash", "Gamma Cash", "Vega Cash", "Theta Cash"),
        vertical_spacing=0.12,
        horizontal_spacing=0.08
    )
    
    # Delta Cash曲线
    fig_combined.add_trace(
        go.Scatter(
            x=prices,
            y=total_delta_cash_curve,
            mode='lines',
            name='Delta Cash',
            line=dict(color='#1f77b4', width=2)
        ),
        row=1, col=1
    )
    
    # Gamma Cash曲线
    fig_combined.add_trace(
        go.Scatter(
            x=prices,
            y=total_gamma_cash_curve,
            mode='lines',
            name='Gamma Cash',
            line=dict(color='#ff7f0e', width=2)
        ),
        row=1, col=2
    )
    
    # Vega Cash曲线
    fig_combined.add_trace(
        go.Scatter(
            x=prices,
            y=total_vega_cash_curve,
            mode='lines',
            name='Vega Cash',
            line=dict(color='#2ca02c', width=2)
        ),
        row=2, col=1
    )
    
    # Theta Cash曲线
    fig_combined.add_trace(
        go.Scatter(
            x=prices,
            y=total_theta_cash_curve,
            mode='lines',
            name='Theta Cash',
            line=dict(color='#d62728', width=2)
        ),
        row=2, col=2
    )
    
    # 为每个子图添加零线和当前价格线
    for row in [1, 2]:
        for col in [1, 2]:
            fig_combined.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5, row=row, col=col)
            fig_combined.add_vline(x=avg_underlying_price, line_dash="dash", line_color="blue", opacity=0.3, row=row, col=col)
    
    # 标记当前价格点
    current_idx = len(prices) // 2  # 中间点作为当前价格
    fig_combined.add_trace(
        go.Scatter(x=[avg_underlying_price], y=[total_delta_cash_curve[current_idx]], 
                   mode='markers', marker=dict(color='red', size=10, symbol='star'), showlegend=False),
        row=1, col=1
    )
    fig_combined.add_trace(
        go.Scatter(x=[avg_underlying_price], y=[total_gamma_cash_curve[current_idx]], 
                   mode='markers', marker=dict(color='red', size=10, symbol='star'), showlegend=False),
        row=1, col=2
    )
    fig_combined.add_trace(
        go.Scatter(x=[avg_underlying_price], y=[total_vega_cash_curve[current_idx]], 
                   mode='markers', marker=dict(color='red', size=10, symbol='star'), showlegend=False),
        row=2, col=1
    )
    fig_combined.add_trace(
        go.Scatter(x=[avg_underlying_price], y=[total_theta_cash_curve[current_idx]], 
                   mode='markers', marker=dict(color='red', size=10, symbol='star'), showlegend=False),
        row=2, col=2
    )
    
    # 更新布局
    fig_combined.update_layout(
        title=f"组合Greeks Cash随标的价格变化 (当前价格: {avg_underlying_price:.4f})",
        height=700,
        showlegend=True
    )
    
    # 更新坐标轴标签
    fig_combined.update_xaxes(title_text="标的价格", row=1, col=1)
    fig_combined.update_xaxes(title_text="标的价格", row=1, col=2)
    fig_combined.update_xaxes(title_text="标的价格", row=2, col=1)
    fig_combined.update_xaxes(title_text="标的价格", row=2, col=2)
    fig_combined.update_yaxes(title_text="元", row=1, col=1)
    fig_combined.update_yaxes(title_text="元", row=1, col=2)
    fig_combined.update_yaxes(title_text="元", row=2, col=1)
    fig_combined.update_yaxes(title_text="元", row=2, col=2)
    
    st.plotly_chart(fig_combined, use_container_width=True)
    
    # 添加一个汇总的叠加图
    st.markdown("---")
    st.subheader("📈 组合Greeks Cash叠加对比")
    
    fig_overlay = go.Figure()
    
    fig_overlay.add_trace(
        go.Scatter(
            x=prices,
            y=total_delta_cash_curve,
            mode='lines',
            name='Delta Cash',
            line=dict(color='#1f77b4', width=2)
        )
    )
    
    fig_overlay.add_trace(
        go.Scatter(
            x=prices,
            y=total_gamma_cash_curve,
            mode='lines',
            name='Gamma Cash',
            line=dict(color='#ff7f0e', width=2)
        )
    )
    
    fig_overlay.add_trace(
        go.Scatter(
            x=prices,
            y=total_vega_cash_curve,
            mode='lines',
            name='Vega Cash',
            line=dict(color='#2ca02c', width=2)
        )
    )
    
    fig_overlay.add_trace(
        go.Scatter(
            x=prices,
            y=total_theta_cash_curve,
            mode='lines',
            name='Theta Cash',
            line=dict(color='#d62728', width=2)
        )
    )
    
    # 添加零线和当前价格线
    fig_overlay.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig_overlay.add_vline(x=avg_underlying_price, line_dash="dash", line_color="blue", opacity=0.5,
                          annotation_text=f"当前价格: {avg_underlying_price:.4f}")
    
    fig_overlay.update_layout(
        title="组合Greeks Cash叠加对比",
        xaxis_title="标的价格",
        yaxis_title="Greeks Cash (元)",
        height=500,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig_overlay, use_container_width=True)

# 说明文档
st.markdown("---")
st.markdown("""
### 📖 使用说明

1. **选择期权合约** (左侧边栏):
   - ① 选择ETF标的 (如300ETF、500ETF、科创50等)
   - ② 选择合约月份 (如1月、2月等)
   - ③ 选择行权价
   - ④ 选择购权(Call)或沽权(Put)
   - ⑤ 选择仓位类型 (权利仓/义务仓)
   - ⑥ 输入持仓张数
   
2. **仓位类型**:
   - **权利仓 (买入)**: Greeks保持原值
   - **义务仓 (卖出)**: Greeks取反

3. **Greeks Cash计算**:
   - **Delta Cash** = Delta × 合约乘数 × 标的价格 × 持仓张数
   - **Gamma Cash** = Gamma × 合约乘数 × 标的价格² × 1% × 持仓张数
   - **Vega Cash** = Vega × 合约乘数 × 持仓张数
   - **Theta Cash** = Theta × 合约乘数 × 持仓张数 ÷ 365 (年化Theta转日化)

### 📌 注意事项

- ETF期权合约乘数默认为 **10,000**
- Delta Cash 表示标的价格变动1元时，组合价值的变动量
- Gamma Cash 表示标的价格变动1%时，Delta Cash的变动量
- Vega Cash 表示隐含波动率变动1%时，组合价值的变动量
- Theta Cash 表示每日的时间价值损耗（原始Theta为年化值，已除以365个自然日）
- 曲线图使用Gamma近似模拟Delta随价格的变化，仅供参考
""")
