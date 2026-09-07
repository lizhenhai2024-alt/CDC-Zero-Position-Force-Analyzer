# CDC Zero Position Force Analyzer

Windows 单机运行的 CDC 减振器试验数据处理工具。

## V1.0 目标

导入 MTS/通用试验数据，自动识别不同 CDC 电流工况，识别复原/压缩方向和完整测量循环，按可配置评价规则提取行程中心附近阻尼力，并支持气体反弹力修正、自由 XY 绘图和 Excel 导出。

## 当前冻结的核心约定

- 原始字段：`Running Time`、`Axial Displacement`、`Axial Load`、`CDC 1 Current FB_1`
- 电流平台自动识别，显示值保留 1 位小数
- 复原载荷：`> 0`
- 压缩载荷：`< 0`
- 运动方向优先根据 `dX/dt` 判断，载荷符号用于一致性校验
- 原始 `Axial Load` 永不覆盖；气体修正生成独立 `Corrected Axial Load`
- 同一电流允许出现多个 Run；Run 与 Cycle 分开管理
- 图形 X/Y 轴字段可自由选择
- 默认导出 `.xlsx`

## 阻尼力评价规则

### Audi Profile

按客户要求：

- 仅使用最后一个完整测量循环
- 自动计算该循环行程中心
- 评价窗口总宽度 = 总行程的 10%
- 即行程中心两侧各 `±5% × Total Stroke`
- 复原结果：窗口内最大正载荷 `max(F)`
- 压缩结果：窗口内最小负载荷 `min(F)`

### Window Mean Profile

用于常规工程分析：

- 中心窗口宽度可配置，例如 `2% / 5% / 10%`
- 复原、压缩分别按运动方向筛选后求均值
- 窗口定义方式必须在界面明确标注（按单边振幅或总行程）

### Zero Crossing Profile

- 目标位置默认 `X = 0 mm`
- 使用相邻点线性插值计算复原/压缩零位载荷
- 可作为窗口法的对照和数据质量检查

## 气体反弹力修正

支持：

1. 不修正
2. 直接输入零位气体反弹力 `Fg`
3. 根据气体表压和活塞杆直径计算零位气体力

恒定气体力修正：

`F_corrected = F_measured - Fg`

## 计划技术栈

- GUI: PySide6
- 数值处理: NumPy / Pandas
- 绘图: PyQtGraph
- Excel: openpyxl
- 打包: PyInstaller

详细需求见 `docs/V1.0_REQUIREMENTS.md`。
