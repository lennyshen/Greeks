# 📊 期权Greeks Cash分析仪表板

一个基于Streamlit构建的ETF期权Greeks Cash分析工具，帮助投资者实时监控和分析期权持仓的风险敞口。

## ✨ 功能特点

- **实时数据**: 通过AKShare获取东方财富网的实时期权数据
- **多品种支持**: 支持上交所和深交所全部9个ETF期权品种
- **Greeks Cash计算**: 自动计算Delta Cash、Gamma Cash、Vega Cash、Theta Cash
- **可视化分析**: 展示Greeks随标的价格变化的趋势曲线
- **持仓管理**: 支持添加、编辑、删除持仓，实时更新分析结果

## 📈 支持的ETF期权品种

### 上交所
- 上证50ETF期权 (510050)
- 沪深300ETF期权 (510300) - 华泰柏瑞
- 中证500ETF期权 (510500) - 南方
- 科创50ETF期权 (588000) - 华夏
- 科创板50ETF期权 (588080) - 易方达

### 深交所
- 创业板ETF期权 (159915)
- 深证100ETF期权 (159901)
- 中证500ETF期权 (159922) - 嘉实
- 沪深300ETF期权 (159919) - 嘉实

## 🚀 快速开始

### 本地运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/Option_Greeks_Dashboard.git
cd Option_Greeks_Dashboard

# 安装依赖
pip install -r requirements.txt

# 运行应用
streamlit run Option_Dashboard.py
```

### Streamlit Cloud部署

> ⚠️ **重要提示**: 由于东方财富网限制海外IP访问，Streamlit Cloud（服务器在美国）可能无法获取数据。建议使用以下替代方案：

**替代方案1: 本地运行** (推荐)
```bash
streamlit run Option_Dashboard.py
```

**替代方案2: 国内云服务器部署**
- 阿里云、腾讯云等国内服务器
- 使用Docker部署

**替代方案3: 使用Streamlit Cloud** (可能无法获取数据)
1. Fork本仓库到你的GitHub账号
2. 登录 [Streamlit Cloud](https://streamlit.io/cloud)
3. 点击 "New app" 并选择你的仓库
4. 设置主文件为 `Option_Dashboard.py`
5. 点击 "Deploy"

## 📊 Greeks Cash 计算公式

| Greeks Cash | 计算公式 | 含义 |
|-------------|----------|------|
| Delta Cash | Delta × 合约乘数 × 标的价格 × 持仓张数 | 标的价格变动1元的盈亏 |
| Gamma Cash | Gamma × 合约乘数 × 标的价格² × 1% × 持仓张数 | 标的价格变动1%时Delta Cash的变化 |
| Vega Cash | Vega × 合约乘数 × 持仓张数 | 波动率变动1%的盈亏 |
| Theta Cash | Theta × 合约乘数 × 持仓张数 ÷ 365 | 每日时间价值损耗 |

> 注: ETF期权合约乘数为10,000

## 🔧 技术栈

- **Frontend**: Streamlit
- **Data**: AKShare, Pandas, NumPy
- **Visualization**: Plotly

## 📝 使用说明

1. **选择期权合约**: 
   - 在左侧边栏依次选择ETF标的、合约月份、行权价、购权/沽权
   - 选择仓位类型（权利仓/义务仓）和持仓张数
   
2. **添加持仓**: 点击"添加到持仓"按钮

3. **查看分析**:
   - 持仓明细表格（可直接编辑张数）
   - Greeks Cash汇总
   - Greeks随标的价格变化的趋势图

4. **管理持仓**: 勾选删除列可批量删除持仓

## ⚠️ 免责声明

本工具仅供学习和研究使用，不构成任何投资建议。期权交易具有高风险，请在充分了解风险的情况下谨慎投资。

## 📄 License

MIT License
