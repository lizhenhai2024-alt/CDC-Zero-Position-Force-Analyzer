# CDC Zero Position Force Analyzer

CDC 减振器台架数据中心行程阻尼力分析工具。当前 `v0.2.0` 已实现核心算法与 PySide6/PyQtGraph 单机 GUI 开发版本。

## 已实现

- MTS `.dat` 重复 `Data Acquisition` 数据块解析
- CSV / XLSX 导入
- CDC 反馈电流自动归一到 0.1 A，并保留实际中位值/标准差
- Run 分段、升/降电流 Sweep 标记
- 基于位移运动方向的复原/压缩识别
- 完整 Cycle 检测，不把 Block 与 Cycle 直接等同
- Audi：最后一个完整循环 + 行程中心总行程 10% 窗口 + 复原最大值 / 压缩最小值
- Window Mean：窗口比例、基准可设置
- Zero Crossing：目标位移线性插值
- 气体反弹力恒定修正，原始载荷永不覆盖
- Summary / Run / Cycle 三级结果
- `.xlsx` 导出
- CLI 调试入口
- PySide6 / PyQtGraph GUI
- X 轴字段自由选择、Y 轴多字段选择
- Current / Run / Cycle 图形筛选
- 不同量纲自动上下分图并共享 X 轴
- Audi 10% 评价窗口与复原/压缩峰值点可视化
- PNG 图形导出

## 安装开发环境

```bash
python -m pip install -e .[dev]
pytest -q
```

GUI：

```bash
python -m pip install -e .[gui]
cdc-analyzer-gui
```

## CLI 示例

Audi 原始载荷：

```bash
cdc-analyzer sample.dat --profile audi
```

气体力修正后评价：

```bash
cdc-analyzer sample.dat --profile audi --gas-force 200 --corrected --export result.xlsx
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
- `Corrected Axial Load = Analysis Axial Load - Gas Force`
- Audi 10% 是评价窗口总宽度，即中心两侧各 `±5% × Total Stroke`

详细需求见 `docs/V1.0_REQUIREMENTS.md`，实测验证见 `docs/VALIDATION_2026-09-07.md`。
