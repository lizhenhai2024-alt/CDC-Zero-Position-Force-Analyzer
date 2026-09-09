from __future__ import annotations

from typing import Any

DEFAULT_LANGUAGE = "zh_CN"
SUPPORTED_LANGUAGES = ("zh_CN", "en_US")

UI_TEXT: dict[str, dict[str, str]] = {
    "zh_CN": {
        "app_title": "CDC 零位阻尼力分析器 v0.5",
        "language_group": "界面语言",
        "data_file": "数据文件",
        "open_file": "打开 DAT / CSV / XLSX",
        "no_file": "未加载文件",
        "rows": "数据行",
        "blocks": "数据块",
        "evaluation": "评价设置",
        "profile": "评价方法",
        "profile_audi": "Audi — 最后完整循环 / 中心10%行程 / 峰值",
        "profile_window": "窗口均值",
        "profile_zero": "目标位移穿越插值",
        "force": "载荷通道",
        "force_raw": "实测载荷",
        "force_corrected": "气体力修正载荷",
        "window": "窗口比例",
        "window_basis": "窗口基准",
        "basis_amplitude": "单边振幅",
        "basis_total": "总行程全宽",
        "target_x": "目标位移 X",
        "gas_group": "气体反弹力修正",
        "mode": "修正方式",
        "gas_operation": "运算方式",
        "gas_subtract": "减去气体反弹力",
        "gas_add": "加上气体反弹力",
        "gas_off": "关闭",
        "gas_direct": "直接输入气体力",
        "gas_pressure_mode": "气压 + 活塞杆直径",
        "gas_force": "气体反弹力",
        "gauge_pressure": "表压",
        "rod_diameter": "活塞杆直径",
        "analyze": "开始分析",
        "plot_group": "图形",
        "x_axis": "X轴",
        "y_axis": "Y轴",
        "current": "电流",
        "run": "工况",
        "cycle": "循环",
        "all": "全部",
        "export": "导出",
        "excel": "Excel",
        "png": "PNG",
        "tab_plot": "图形",
        "tab_summary": "汇总结果",
        "tab_run": "工况明细",
        "tab_cycle": "循环明细",
        "tab_sweep": "升/降电流对比",
        "tab_quality": "数据质量",
        "ready": "就绪",
        "open_test_data": "打开试验数据",
        "test_data_filter": "试验数据 (*.dat *.csv *.xlsx *.xlsm);;所有文件 (*)",
        "import_error": "导入错误",
        "analysis_error": "分析错误",
        "data_quality_error": "数据质量错误",
        "data_quality_error_body": "原始数据预检发现结构性错误。请先查看“数据质量”页中的问题，再进行分析。",
        "analysis_blocked": "分析已阻止：原始数据质量为 Invalid",
        "analysis_complete": "分析完成：{runs} 个工况，{cycles} 个完整循环，{warnings} 个警告",
        "analysis_complete_v04": "分析完成：{runs} 个工况，{cycles} 个完整循环，{warnings} 个工况警告 | 数据质量：{quality} | {paired} 个升/降电流配对档位",
        "export_excel": "导出 Excel",
        "export_plot": "导出图形",
        "exported": "已导出：{path}",
        "plot_exported": "图形已导出：{path}",
        "export_error": "导出错误",
    },
    "en_US": {
        "app_title": "CDC Zero Position Force Analyzer v0.5",
        "language_group": "UI Language",
        "data_file": "Data file",
        "open_file": "Open DAT / CSV / XLSX",
        "no_file": "No file loaded",
        "rows": "Rows",
        "blocks": "Blocks",
        "evaluation": "Evaluation",
        "profile": "Profile",
        "profile_audi": "Audi — Last complete cycle / 10% center stroke / Peak",
        "profile_window": "Window Mean",
        "profile_zero": "Target-position crossing interpolation",
        "force": "Force channel",
        "force_raw": "Measured load",
        "force_corrected": "Gas-corrected load",
        "window": "Window",
        "window_basis": "Window basis",
        "basis_amplitude": "Single-sided amplitude",
        "basis_total": "Total-stroke full width",
        "target_x": "Target X",
        "gas_group": "Gas rebound-force correction",
        "mode": "Mode",
        "gas_operation": "Operation",
        "gas_subtract": "Subtract gas force",
        "gas_add": "Add gas force",
        "gas_off": "Off",
        "gas_direct": "Direct force",
        "gas_pressure_mode": "Pressure + rod diameter",
        "gas_force": "Gas force",
        "gauge_pressure": "Gauge pressure",
        "rod_diameter": "Rod diameter",
        "analyze": "Analyze",
        "plot_group": "Plot",
        "x_axis": "X axis",
        "y_axis": "Y axis",
        "current": "Current",
        "run": "Run",
        "cycle": "Cycle",
        "all": "All",
        "export": "Export",
        "excel": "Excel",
        "png": "PNG",
        "tab_plot": "Plot",
        "tab_summary": "Summary",
        "tab_run": "Run Detail",
        "tab_cycle": "Cycle Detail",
        "tab_sweep": "Sweep Comparison",
        "tab_quality": "Data Quality",
        "ready": "Ready",
        "open_test_data": "Open test data",
        "test_data_filter": "Test data (*.dat *.csv *.xlsx *.xlsm);;All files (*)",
        "import_error": "Import error",
        "analysis_error": "Analysis error",
        "data_quality_error": "Data quality error",
        "data_quality_error_body": "Raw-data preflight found a structural error. Open the Data Quality tab for details before analysis.",
        "analysis_blocked": "Analysis blocked: raw-data quality is Invalid",
        "analysis_complete": "Analysis complete: {runs} runs, {cycles} complete cycles, {warnings} warnings",
        "analysis_complete_v04": "Analysis complete: {runs} runs, {cycles} complete cycles, {warnings} run warnings | Data quality: {quality} | {paired} paired sweep levels",
        "export_excel": "Export Excel",
        "export_plot": "Export plot",
        "exported": "Exported: {path}",
        "plot_exported": "Plot exported: {path}",
        "export_error": "Export error",
    },
}

CHANNEL_ZH = {
    "Running Time": "运行时间",
    "Axial Displacement": "轴向位移",
    "Axial Load": "轴向载荷",
    "CDC 1 Current FB_1": "CDC 1 反馈电流",
    "Analysis Axial Load": "分析轴向载荷",
    "Gas Force": "气体反弹力",
    "Gas Force Correction": "气体力修正量",
    "Corrected Axial Load": "修正轴向载荷",
    "Motion Direction": "运动方向",
    "Current Label": "电流档位",
    "Current Actual": "实际电流",
    "Sweep Direction": "电流扫描方向",
    "Run ID": "工况编号",
    "Cycle ID": "循环编号",
    "Block ID": "数据块编号",
    "Source Row": "源数据行号",
}

COLUMN_ZH = {
    **CHANNEL_ZH,
    "Global Cycle ID": "全局循环编号",
    "Current Label A": "电流档位 A",
    "Current Actual A": "实际电流 A",
    "Current Std A": "电流标准差 A",
    "Duration s": "持续时间 s",
    "Complete Cycle Count": "完整循环数",
    "Selected Cycle ID": "选用循环编号",
    "Rebound N": "复原载荷 N",
    "Compression N": "压缩载荷 N",
    "Rebound SD N": "复原标准差 N",
    "Compression SD N": "压缩标准差 N",
    "Run Count": "工况数",
    "Status": "状态",
    "Issues": "问题",
    "Evaluation Profile": "评价方法",
    "Force Channel": "载荷通道",
    "Complete": "完整循环",
    "Center Position mm": "中心位置 mm",
    "Total Stroke mm": "总行程 mm",
    "Start Time s": "开始时间 s",
    "End Time s": "结束时间 s",
    "Window Low mm": "窗口下限 mm",
    "Window High mm": "窗口上限 mm",
    "Window Basis": "窗口基准",
    "Rebound Point Count": "复原点数",
    "Compression Point Count": "压缩点数",
    "Sample Count": "采样点数",
    "Finite Sample Count": "有效采样点数",
    "Median dt s": "中位采样间隔 s",
    "Sample Rate Hz": "采样频率 Hz",
    "Max dt s": "最大采样间隔 s",
    "Max/Median dt": "最大/中位采样间隔",
    "Displacement Min mm": "最小位移 mm",
    "Displacement Max mm": "最大位移 mm",
    "Displacement Span mm": "位移跨度 mm",
    "Median |dX| mm": "中位 |dX| mm",
    "Max |dX| mm": "最大 |dX| mm",
    "Load Min N": "最小载荷 N",
    "Load Max N": "最大载荷 N",
    "Current Median A": "电流中位值 A",
    "Up Rebound N": "升电流复原 N",
    "Down Rebound N": "降电流复原 N",
    "Delta Rebound N": "复原差值 N",
    "Up Compression N": "升电流压缩 N",
    "Down Compression N": "降电流压缩 N",
    "Delta Compression N": "压缩差值 N",
    "Up Run Count": "升电流工况数",
    "Down Run Count": "降电流工况数",
    "Coverage": "覆盖情况",
}

VALUE_ZH = {
    "OK": "正常",
    "Warning": "警告",
    "Invalid": "无效",
    "Rebound": "复原",
    "Compression": "压缩",
    "Unknown": "未知",
    "Up": "升电流",
    "Down": "降电流",
    "Hold": "保持",
    "Up + Down": "升 + 降",
    "Up only": "仅升电流",
    "Down only": "仅降电流",
    "raw": "实测载荷",
    "corrected": "气体力修正载荷",
    "audi": "Audi",
    "window_mean": "窗口均值",
    "zero_crossing": "目标位移穿越插值",
    "10% total stroke (Audi)": "中心10%总行程（Audi）",
}

ISSUE_ZH = {
    "too few samples": "采样点过少",
    "missing evaluation data": "缺少评价数据",
    "insufficient rebound window points": "复原窗口采样点不足",
    "insufficient compression window points": "压缩窗口采样点不足",
    "unexpected rebound force sign": "复原载荷符号异常",
    "unexpected compression force sign": "压缩载荷符号异常",
    "run too short": "工况持续时间过短",
    "current unstable": "电流不稳定",
    "no complete cycle": "未识别到完整循环",
}


def tr(language: str, key: str) -> str:
    lang = language if language in UI_TEXT else DEFAULT_LANGUAGE
    return UI_TEXT[lang].get(key, UI_TEXT["en_US"].get(key, key))


def display_channel(language: str, name: str) -> str:
    return CHANNEL_ZH.get(name, name) if language == "zh_CN" else name


def display_column(language: str, name: str) -> str:
    return COLUMN_ZH.get(name, name) if language == "zh_CN" else name


def _translate_issue_piece(text: str) -> str:
    stripped = text.strip()
    if stripped in ISSUE_ZH:
        return ISSUE_ZH[stripped]
    prefixes = {
        "non-finite samples:": "非有限数值采样点：",
        "non-increasing time intervals:": "时间不递增区间：",
        "large time gap ratio:": "采样时间大间隙比：",
    }
    for prefix, translated in prefixes.items():
        if stripped.startswith(prefix):
            return translated + stripped[len(prefix):]
    return stripped


def display_value(language: str, column: str, value: Any) -> Any:
    if language != "zh_CN" or value is None:
        return value
    if column == "Issues" and isinstance(value, str):
        return "; ".join(_translate_issue_piece(piece) for piece in value.split(";") if piece.strip())
    if isinstance(value, str):
        return VALUE_ZH.get(value, value)
    return value
