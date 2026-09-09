# CDC Test Data Analyzer

富奥东机工减振器有限公司（FAWER-TOKICO SHOCK ABSORBER CO., LTD.）CDC / 电控减振器台架数据分析工具。

- 编制：研发院技术中心　李振海
- 发布日期：2026/9/7
- 发布：第1版
- Python package version：`1.0.0`

## 核心功能

- MTS `.dat` 重复 `Data Acquisition` 数据块解析
- CSV / XLSX 导入
- CDC 反馈电流自动归一到 0.1 A，并保留实际中位值/标准差
- Run 分段、升/降电流 Sweep 标记
- 基于位移运动方向的复原/压缩识别
- 完整 Cycle 检测，不把 Block 与 Cycle 直接等同
- Audi：最后一个完整循环 + 行程中心总行程 10% 窗口 + 复原最大值 / 压缩最小值
- Window Mean：窗口比例、基准可设置
- Zero Crossing：目标位移线性插值
- 气体反弹力支持“加上 / 减去”恒定修正，原始载荷永不覆盖
- 响应分析的客户 Profile 与目标速度独立设置，支持 0.1、0.3、0.6、1.0 m/s 等任意正有限速度点
- 响应时间统一以 I₁₀% 电流交点为零点，输出 t₁%、t₆₃%、t₉₀% = 对应力阈值交点时刻 − I₁₀% 交点时刻
- 响应图文字采用透明背景、常规字重并与坐标轴标题同字号；电流/载荷图的垂直参考线在实测曲线交点显示圆点，时间文字沿竖线在交点正上方或正下方布置；载荷显示范围覆盖 F₁₀₀% 计算窗口
- Summary / Run / Cycle 三级结果
- Data Quality：按 acquisition block 输出采样点数、采样率、时间间隔、位移范围、载荷范围、电流中位数/标准差及结构性异常
- GUI 分析前执行 Data Quality preflight；结构性 `Invalid` 输入停止分析
- Sweep Comparison：保留 Up / Down 结果并输出 `Delta = Down - Up`
- X 轴字段自由选择、Y 轴多字段选择
- Current / Run / Cycle 图形筛选
- 不同量纲自动上下分图并共享 X 轴
- Audi 10% 评价窗口与复原/压缩峰值点可视化
- 图形背景：白色、黑色、浅灰、深灰及自定义颜色
- 图形工具：放大、缩小、框选放大、平移、恢复、滚轮缩放
- 中文 / English 界面实时切换，**默认中文**
- 专业帮助页面：使用流程、评价算法、符号约定、气体力修正、Data Quality、Sweep、图形工具、常见问题及工程边界
- `.xlsx` 与 PNG 导出
- Windows x86-64 单文件 EXE 自动构建

## 品牌信息

Windows 构建流程从富奥东机工减振器有限公司官方网站 `https://www.faw-tokico.com/` 自动获取官方 Logo，并将获取到的 Logo 与来源信息打包进入 EXE。构建阶段会记录实际 Logo 资源 URL，避免使用第三方网站图片。

## 数据质量原则

质量模块只对可客观判断的数据结构问题给出 Warning / Invalid，例如：

- 必需通道出现 NaN / Inf
- 时间戳不递增或重复
- 数据点过少
- 相邻采样时间出现明显大间隙

采样频率、位移步长以及升/降电流差异同时作为工程诊断指标输出，但在没有客户限值时不擅自判定合格/不合格。

## 安装开发环境

```bash
python -m pip install -e ".[dev,gui]"
pytest -q
cdc-analyzer-gui
```

## CLI 示例

Audi 原始载荷：

```bash
cdc-analyzer sample.dat --profile audi
```

气体力修正后评价：

```bash
cdc-analyzer sample.dat --profile audi --gas-force 200 --gas-operation subtract --corrected --export result.xlsx
```

2% 单边振幅窗口均值：

```bash
cdc-analyzer sample.dat --profile window_mean --window-percent 2 --window-basis amplitude
```

## 重要约定

- 复原：`dX/dt > 0`，载荷期望 `> 0`
- 压缩：`dX/dt < 0`，载荷期望 `< 0`
- 电流工况标签显示保留 1 位小数
- 复原/压缩载荷结果显示保留整数 N
- 其它连续量显示保留 2 位小数
- 显示舍入不改变内部计算精度
- 气体力运算可选择 `Corrected Axial Load = Analysis Axial Load - Gas Force` 或 `Corrected Axial Load = Analysis Axial Load + Gas Force`
- Audi 10% 是评价窗口总宽度，即中心两侧各 `±5% × Total Stroke`
- Sweep Comparison 的 `Delta` 定义为 `Down - Up`
- Sweep 差异只做描述性输出，除非后续提供明确工程或客户限值
- `t₉₀%限值` 为项目可选限值；未设置时只报告测量值，不自动判定合格性

详细需求见 `docs/V1.0_REQUIREMENTS.md`；基础实测验证见 `docs/VALIDATION_2026-09-07.md`；V0.4 验证见 `docs/VALIDATION_V0.4_2026-09-07.md`；V0.8.4 绘图规则见 `docs/V0.8.4_RESPONSE_MARKER_LAYOUT.md`。