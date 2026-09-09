from __future__ import annotations

import sys

from .gui import _qt_imports
from .gui_v04 import _build_gui_classes_v04


TEXT = {
    "zh_CN": {
        "background": "图形背景",
        "white": "白色",
        "black": "黑色",
        "light_gray": "浅灰色",
        "dark_gray": "深灰色",
        "custom": "其它颜色…",
        "choose_color": "选择图形背景颜色",
        "zoom_in": "放大",
        "zoom_out": "缩小",
        "box_zoom": "框选放大",
        "pan": "平移",
        "reset": "恢复",
        "zoom_in_tip": "以当前图形中心为基准放大",
        "zoom_out_tip": "以当前图形中心为基准缩小",
        "box_zoom_tip": "拖动鼠标框选区域并放大",
        "pan_tip": "拖动鼠标平移图形",
        "reset_tip": "恢复到当前筛选数据的全部范围",
        "help_tab": "专业帮助",
        "help_button": "帮助 / 使用说明",
    },
    "en_US": {
        "background": "Plot background",
        "white": "White",
        "black": "Black",
        "light_gray": "Light gray",
        "dark_gray": "Dark gray",
        "custom": "Custom color…",
        "choose_color": "Choose plot background color",
        "zoom_in": "Zoom In",
        "zoom_out": "Zoom Out",
        "box_zoom": "Box Zoom",
        "pan": "Pan",
        "reset": "Reset",
        "zoom_in_tip": "Zoom in around the current plot center",
        "zoom_out_tip": "Zoom out around the current plot center",
        "box_zoom_tip": "Drag a rectangle to zoom into a selected region",
        "pan_tip": "Drag the mouse to pan the plot",
        "reset_tip": "Restore the full range of the currently filtered data",
        "help_tab": "Professional Help",
        "help_button": "Help / User Guide",
    },
}

BACKGROUND_PRESETS = {
    "white": "#ffffff",
    "black": "#000000",
    "light_gray": "#f2f2f2",
    "dark_gray": "#303030",
}


def _t(language: str, key: str) -> str:
    return TEXT.get(language, TEXT["en_US"]).get(key, key)


def _help_html(language: str) -> str:
    if language == "zh_CN":
        return """
        <html><head><style>
        body { font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif; line-height: 1.55; margin: 22px; color: #202020; }
        h1 { font-size: 24px; margin-bottom: 6px; }
        h2 { font-size: 18px; margin-top: 24px; border-bottom: 1px solid #cfcfcf; padding-bottom: 5px; }
        h3 { font-size: 15px; margin-top: 18px; }
        table { border-collapse: collapse; width: 100%; margin: 10px 0 16px 0; }
        th, td { border: 1px solid #bdbdbd; padding: 6px 8px; vertical-align: top; }
        th { background: #eeeeee; }
        code { font-family: Consolas, monospace; background: #f3f3f3; padding: 1px 4px; }
        .note { background: #eef6ff; border-left: 4px solid #3c78d8; padding: 9px 12px; margin: 10px 0; }
        .warn { background: #fff6e5; border-left: 4px solid #d69200; padding: 9px 12px; margin: 10px 0; }
        </style></head><body>
        <h1>CDC 零位阻尼力分析器 — 专业帮助</h1>
        <p>用于 CDC/电控减振器 MTS 等台架数据的中心行程阻尼力评价、气体反弹力修正、升降电流对比和可追溯数据质量检查。</p>

        <h2>1. 推荐工作流程</h2>
        <ol>
          <li>打开 DAT / CSV / XLSX 原始数据。</li>
          <li>先查看“数据质量”，确认不存在结构性 <b>无效</b> 项。</li>
          <li>选择客户/工程评价方法与载荷通道。</li>
          <li>如需要，输入气体反弹力或气压与活塞杆直径。</li>
          <li>执行分析，检查“汇总结果”“工况明细”“循环明细”。</li>
          <li>使用“升/降电流对比”检查电流扫描路径差异。</li>
          <li>在图形页检查 F-X 滞环、评价窗口和选取点，再导出 Excel/PNG。</li>
        </ol>

        <h2>2. 数据与符号约定</h2>
        <table>
          <tr><th>项目</th><th>程序约定</th></tr>
          <tr><td>复原</td><td><code>dX/dt &gt; 0</code>，载荷期望为正值</td></tr>
          <tr><td>压缩</td><td><code>dX/dt &lt; 0</code>，载荷期望为负值</td></tr>
          <tr><td>电流档位</td><td>根据 CDC 反馈电流自动识别，主显示保留 1 位小数</td></tr>
          <tr><td>Run / 工况</td><td>同一电流允许出现多个独立工况；不与 Cycle 混同</td></tr>
          <tr><td>Cycle / 循环</td><td>根据位移极值和完整行程自动识别完整往复循环</td></tr>
        </table>
        <div class="note">运动方向由位移变化判断，载荷正负用于一致性校验，程序不会用载荷符号代替运动方向。</div>

        <h2>3. 阻尼力评价方法</h2>
        <h3>Audi</h3>
        <p>使用该工况的<b>最后一个完整测量循环</b>。以该循环的实际行程中心为中心，建立<b>总行程 10%</b> 的评价窗口，即中心两侧各 ±5% × Total Stroke。</p>
        <ul>
          <li>复原结果：窗口内最大正载荷。</li>
          <li>压缩结果：窗口内最小负载荷。</li>
        </ul>
        <h3>窗口均值</h3>
        <p>在中心附近的可配置窗口内，将复原与压缩数据按运动方向分开后分别求均值。窗口比例与基准可设置。</p>
        <h3>目标位移穿越插值</h3>
        <p>默认目标位置 X=0 mm。程序寻找跨越目标位移的相邻采样点，对复原、压缩分别进行线性插值。</p>

        <h2>4. 气体反弹力修正</h2>
        <p>原始轴向载荷永不覆盖。修正后生成独立载荷通道：</p>
        <p>运算方式可选择：</p>
        <p><code>Corrected Load = Measured Load - Gas Force</code></p>
        <p>或 <code>Corrected Load = Measured Load + Gas Force</code></p>
        <p>若使用气压计算：<code>Fg = Pg × π × d² / 4</code>，其中 Pg 使用表压（MPa），d 使用 mm，结果为 N。</p>
        <div class="warn">零位恒定气体力适合中心行程评价；若未来需要全行程精确修正，应使用随位移变化的气体状态模型。</div>

        <h2>5. 图形与工具栏</h2>
        <table>
          <tr><th>工具</th><th>作用</th></tr>
          <tr><td>放大 / 缩小</td><td>围绕当前视图中心调整显示范围。</td></tr>
          <tr><td>框选放大</td><td>进入矩形缩放模式，拖动鼠标框选关注区域。</td></tr>
          <tr><td>平移</td><td>拖动鼠标移动当前视图。</td></tr>
          <tr><td>恢复</td><td>恢复当前筛选数据的全部范围。</td></tr>
          <tr><td>鼠标滚轮</td><td>PyQtGraph 原生滚轮缩放仍可使用。</td></tr>
          <tr><td>背景</td><td>白色、黑色、浅灰、深灰或任意自定义颜色；PNG 导出沿用当前背景。</td></tr>
        </table>
        <p>导入新数据后，X 轴默认选择第 1 个可绘制的原始数据列，Y 轴默认选择其余原始数据列。重新分析同一文件时保留手动选择；不同量纲的多个 Y 字段自动采用上下分图并共享 X 轴。</p>

        <h2>6. 数据质量页面</h2>
        <p>按原始 Acquisition Block 输出采样点数、采样频率、时间间隔、位移范围、载荷范围、电流中位值与标准差等。结构性错误会阻止工程评价，例如：</p>
        <ul><li>必需通道 NaN / Inf</li><li>时间戳重复或倒退</li><li>采样点过少</li><li>明显的大时间间隙</li></ul>
        <p>没有客户限值时，采样频率等指标只报告，不擅自判定客户合格/不合格。</p>

        <h2>7. 升/降电流对比</h2>
        <p>同一电流分别保存 Up 和 Down 工况结果，差值定义为：</p>
        <p><code>Delta = Down - Up</code></p>
        <p>转折点只有一个方向时显示“仅升电流”或“仅降电流”，不制造不存在的配对结果。差值为诊断量，除非输入明确限值，否则不自动判定合格性。</p>

        <h2>8. 数值显示与导出</h2>
        <ul>
          <li>复原/压缩载荷：显示为整数 N。</li>
          <li>电流档位：1 位小数 A。</li>
          <li>其它连续量：2 位小数。</li>
          <li>显示舍入不改变内部计算精度。</li>
        </ul>
        <p>Excel 包含汇总、工况明细、循环明细、升/降电流对比、数据质量和设置等信息；必要时可包含处理后原始数据。</p>

        <h2>9. 常见问题</h2>
        <table>
          <tr><th>现象</th><th>优先检查</th></tr>
          <tr><td>没有结果</td><td>是否识别到完整循环；是否存在数据质量 Invalid。</td></tr>
          <tr><td>复原为负 / 压缩为正</td><td>试验机载荷符号、位移方向、传感器方向。</td></tr>
          <tr><td>窗口点数过少</td><td>导出采样率、窗口宽度、试验速度。</td></tr>
          <tr><td>同电流两次结果差异大</td><td>查看升/降电流对比、电流稳定度、温度、压力建立过程和循环稳定性。</td></tr>
        </table>

        <h2>10. 工程边界</h2>
        <p>本软件用于试验数据工程评价与可追溯分析，不替代客户原始规范。客户规范、试验程序或签署要求与软件默认值不一致时，应以受控版本客户文件为准并调整评价参数。</p>
        </body></html>
        """

    return """
    <html><head><style>
    body { font-family: 'Segoe UI', sans-serif; line-height: 1.55; margin: 22px; color: #202020; }
    h1 { font-size: 24px; } h2 { font-size: 18px; margin-top: 24px; border-bottom: 1px solid #cfcfcf; padding-bottom: 5px; }
    h3 { font-size: 15px; margin-top: 18px; } table { border-collapse: collapse; width: 100%; margin: 10px 0 16px 0; }
    th, td { border: 1px solid #bdbdbd; padding: 6px 8px; vertical-align: top; } th { background: #eeeeee; }
    code { font-family: Consolas, monospace; background: #f3f3f3; padding: 1px 4px; }
    .note { background: #eef6ff; border-left: 4px solid #3c78d8; padding: 9px 12px; margin: 10px 0; }
    .warn { background: #fff6e5; border-left: 4px solid #d69200; padding: 9px 12px; margin: 10px 0; }
    </style></head><body>
    <h1>CDC Zero Position Force Analyzer — Professional Help</h1>
    <p>Engineering analysis for CDC/electronic damper MTS-type test data, including center-stroke force evaluation, gas-force correction, sweep comparison, plotting and traceable data-quality checks.</p>
    <h2>1. Recommended workflow</h2>
    <ol><li>Open DAT / CSV / XLSX raw data.</li><li>Review Data Quality first.</li><li>Select the customer/engineering evaluation profile and force channel.</li><li>Enter gas rebound force if correction is required.</li><li>Analyze and review Summary, Run Detail and Cycle Detail.</li><li>Review Sweep Comparison.</li><li>Verify F-X plots and evaluation windows, then export Excel/PNG.</li></ol>
    <h2>2. Sign convention</h2>
    <p>Rebound: <code>dX/dt &gt; 0</code>, expected force &gt; 0. Compression: <code>dX/dt &lt; 0</code>, expected force &lt; 0. Motion direction is determined from displacement; force sign is a consistency check.</p>
    <h2>3. Evaluation profiles</h2>
    <h3>Audi</h3><p>Last complete measured cycle; evaluation window total width = 10% of total stroke, centered on the measured stroke center. Rebound uses the maximum positive force; compression uses the minimum negative force.</p>
    <h3>Window Mean</h3><p>Separately averages rebound and compression samples inside a configurable center window.</p>
    <h3>Target-position crossing</h3><p>Linearly interpolates rebound and compression force at the selected target displacement, normally 0 mm.</p>
    <h2>4. Gas rebound-force correction</h2>
    <p>Select either <code>Corrected Load = Measured Load - Gas Force</code> or <code>Corrected Load = Measured Load + Gas Force</code>. Pressure calculation uses <code>Fg = Pg × π × d² / 4</code>, with gauge pressure in MPa and rod diameter in mm.</p>
    <h2>5. Plot tools</h2>
    <p>After a new data file is imported, the first plottable source column is selected as X and all remaining source columns are selected as Y. Reanalyzing the same file preserves manual selections. Zoom In, Zoom Out, Box Zoom, Pan and Reset are available above the plot. Mouse-wheel zoom remains available. Background can be White, Black, Light Gray, Dark Gray or a custom color, and PNG export uses the active plot background.</p>
    <h2>6. Data quality</h2>
    <p>Reports sample count/rate, time intervals, displacement/load ranges, current median/std and structural problems by acquisition block. Structural Invalid input blocks engineering analysis. Sampling rate is reported but not judged against an unstated customer limit.</p>
    <h2>7. Sweep comparison</h2>
    <p>Up and Down results are retained separately. <code>Delta = Down - Up</code>. Single-direction turning points remain unpaired. No pass/fail limit is invented without an explicit requirement.</p>
    <h2>8. Display precision</h2>
    <p>Rebound/compression force: integer N; current label: 1 decimal A; other continuous values: 2 decimals. Display rounding never changes internal calculation precision.</p>
    <h2>9. Engineering boundary</h2>
    <p>The software supports engineering evaluation and traceability. Controlled customer specifications remain authoritative whenever their requirements differ from software defaults.</p>
    </body></html>
    """


def _build_gui_classes_v05():
    QtCore, QtWidgets, pg = _qt_imports()
    BaseMainWindow = _build_gui_classes_v04()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self._plot_background_key = "white"
            self._plot_background_color = BACKGROUND_PRESETS["white"]
            self._plot_foreground_color = "#202020"
            self._mouse_mode = "pan"
            super().__init__()
            self._build_v05_ui()
            self._apply_v05_language()
            self._apply_plot_background(refresh=False)

        def _build_v05_ui(self):
            self.background_combo = QtWidgets.QComboBox()
            for key in ("white", "black", "light_gray", "dark_gray", "custom"):
                self.background_combo.addItem("", key)
            self.background_combo.setCurrentIndex(self.background_combo.findData("white"))
            self.background_combo.currentIndexChanged.connect(self._background_changed)
            self.plot_form.addRow("", self.background_combo)

            self.plot_toolbar = QtWidgets.QWidget()
            toolbar_layout = QtWidgets.QHBoxLayout(self.plot_toolbar)
            toolbar_layout.setContentsMargins(0, 0, 0, 4)
            toolbar_layout.setSpacing(6)
            self.zoom_in_button = QtWidgets.QPushButton()
            self.zoom_out_button = QtWidgets.QPushButton()
            self.box_zoom_button = QtWidgets.QPushButton()
            self.pan_button = QtWidgets.QPushButton()
            self.reset_view_button = QtWidgets.QPushButton()
            self.box_zoom_button.setCheckable(True)
            self.pan_button.setCheckable(True)
            self.pan_button.setChecked(True)
            mode_group = QtWidgets.QButtonGroup(self)
            mode_group.setExclusive(True)
            mode_group.addButton(self.box_zoom_button)
            mode_group.addButton(self.pan_button)
            self._plot_mode_group = mode_group
            for button in (
                self.zoom_in_button,
                self.zoom_out_button,
                self.box_zoom_button,
                self.pan_button,
                self.reset_view_button,
            ):
                toolbar_layout.addWidget(button)
            toolbar_layout.addStretch(1)
            self.plot_page.layout().insertWidget(0, self.plot_toolbar)

            self.zoom_in_button.clicked.connect(lambda: self._zoom_view(0.80))
            self.zoom_out_button.clicked.connect(lambda: self._zoom_view(1.25))
            self.box_zoom_button.clicked.connect(lambda: self._set_mouse_mode("rect"))
            self.pan_button.clicked.connect(lambda: self._set_mouse_mode("pan"))
            self.reset_view_button.clicked.connect(self._reset_view)

            self.help_page = QtWidgets.QWidget()
            help_layout = QtWidgets.QVBoxLayout(self.help_page)
            self.help_browser = QtWidgets.QTextBrowser()
            self.help_browser.setOpenExternalLinks(True)
            help_layout.addWidget(self.help_browser)
            self.tabs.addTab(self.help_page, "")

            self.help_button = QtWidgets.QPushButton()
            self.help_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.help_page))
            language_layout = self.language_box.layout()
            if isinstance(language_layout, QtWidgets.QFormLayout):
                language_layout.addRow(self.help_button)

        def _change_language(self):
            super()._change_language()
            if hasattr(self, "help_page"):
                self._apply_v05_language()

        def _apply_v05_language(self):
            if not hasattr(self, "background_combo"):
                return
            label = self.plot_form.labelForField(self.background_combo)
            if label is not None:
                label.setText(_t(self.language, "background"))
            for i, key in enumerate(("white", "black", "light_gray", "dark_gray", "custom")):
                self.background_combo.setItemText(i, _t(self.language, key))
            self.zoom_in_button.setText(_t(self.language, "zoom_in"))
            self.zoom_out_button.setText(_t(self.language, "zoom_out"))
            self.box_zoom_button.setText(_t(self.language, "box_zoom"))
            self.pan_button.setText(_t(self.language, "pan"))
            self.reset_view_button.setText(_t(self.language, "reset"))
            self.zoom_in_button.setToolTip(_t(self.language, "zoom_in_tip"))
            self.zoom_out_button.setToolTip(_t(self.language, "zoom_out_tip"))
            self.box_zoom_button.setToolTip(_t(self.language, "box_zoom_tip"))
            self.pan_button.setToolTip(_t(self.language, "pan_tip"))
            self.reset_view_button.setToolTip(_t(self.language, "reset_tip"))
            self.help_button.setText(_t(self.language, "help_button"))
            self.tabs.setTabText(self.tabs.indexOf(self.help_page), _t(self.language, "help_tab"))
            self.help_browser.setHtml(_help_html(self.language))

        def _background_changed(self):
            key = self.background_combo.currentData()
            if key == "custom":
                color = QtWidgets.QColorDialog.getColor()
                if not color.isValid():
                    index = self.background_combo.findData(self._plot_background_key)
                    self.background_combo.blockSignals(True)
                    self.background_combo.setCurrentIndex(index if index >= 0 else 0)
                    self.background_combo.blockSignals(False)
                    return
                self._plot_background_key = "custom"
                self._plot_background_color = color.name()
            else:
                self._plot_background_key = str(key)
                self._plot_background_color = BACKGROUND_PRESETS.get(str(key), "#ffffff")
            self._apply_plot_background(refresh=True)

        @staticmethod
        def _foreground_for_background(color: str) -> str:
            text = color.lstrip("#")
            if len(text) != 6:
                return "#202020"
            r, g, b = int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            return "#f0f0f0" if luminance < 130 else "#202020"

        def _plot_items(self):
            layout = getattr(self.plot_area, "ci", None)
            items = getattr(layout, "items", {}) if layout is not None else {}
            return [item for item in items.keys() if isinstance(item, pg.PlotItem)]

        def _apply_plot_background(self, refresh: bool = False):
            self._plot_foreground_color = self._foreground_for_background(self._plot_background_color)
            self.plot_area.setBackground(self._plot_background_color)
            if refresh and self.result is not None:
                self.refresh_plot()
                return
            for plot in self._plot_items():
                for axis_name in ("bottom", "left"):
                    axis = plot.getAxis(axis_name)
                    axis.setPen(pg.mkPen(self._plot_foreground_color))
                    axis.setTextPen(pg.mkPen(self._plot_foreground_color))

        def _style_plot(self, plot, x, y):
            super()._style_plot(plot, x, y)
            for axis_name in ("bottom", "left"):
                axis = plot.getAxis(axis_name)
                axis.setPen(pg.mkPen(self._plot_foreground_color))
                axis.setTextPen(pg.mkPen(self._plot_foreground_color))

        def refresh_plot(self):
            super().refresh_plot()
            if not hasattr(self, "_plot_background_color"):
                return
            self._apply_plot_background(refresh=False)
            self._apply_mouse_mode()

        def _zoom_view(self, factor: float):
            plots = self._plot_items()
            if not plots:
                return
            x_range = plots[0].viewRange()[0]
            cx = (x_range[0] + x_range[1]) / 2.0
            hx = (x_range[1] - x_range[0]) * factor / 2.0
            plots[0].setXRange(cx - hx, cx + hx, padding=0)
            for plot in plots:
                y_range = plot.viewRange()[1]
                cy = (y_range[0] + y_range[1]) / 2.0
                hy = (y_range[1] - y_range[0]) * factor / 2.0
                plot.setYRange(cy - hy, cy + hy, padding=0)

        def _set_mouse_mode(self, mode: str):
            self._mouse_mode = mode
            self._apply_mouse_mode()

        def _apply_mouse_mode(self):
            mode = pg.ViewBox.RectMode if self._mouse_mode == "rect" else pg.ViewBox.PanMode
            for plot in self._plot_items():
                plot.getViewBox().setMouseMode(mode)

        def _reset_view(self):
            for plot in self._plot_items():
                plot.enableAutoRange(x=True, y=True)
                plot.autoRange()

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_gui_classes_v05()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("CDC Zero Position Force Analyzer")
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
