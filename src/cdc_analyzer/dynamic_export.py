from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from .dynamic_analysis import HysteresisAnalysisResult, ResponseAnalysisResult
from .formatting import excel_number_format

FigureSpec = tuple[str, str | Path]


def _autosize(ws) -> None:
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for index, cells in enumerate(ws.columns, start=1):
        width = 10
        for cell in cells:
            if cell.value is not None:
                width = max(width, min(len(str(cell.value)) + 2, 42))
        ws.column_dimensions[get_column_letter(index)].width = width


def _format_numbers(ws) -> None:
    if ws.max_row < 2:
        return
    for col in range(1, ws.max_column + 1):
        header = ws.cell(1, col).value
        if not isinstance(header, str):
            continue
        fmt = excel_number_format(header)
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row, col)
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                cell.number_format = fmt


def _settings_frame(settings: dict[str, object], language: str = "en_US") -> pd.DataFrame:
    if language == "zh_CN":
        return pd.DataFrame([{"设置项": key, "值": value} for key, value in settings.items()])
    return pd.DataFrame([{"Setting": key, "Value": value} for key, value in settings.items()])


def _sheet_names(language: str) -> dict[str, str]:
    if language == "zh_CN":
        return {
            "response_summary": "响应汇总",
            "response_figures": "阶段图形",
            "response_overview": "全流程总览",
            "hysteresis_summary": "迟滞汇总",
            "run_detail": "工况明细",
            "hysteresis_figures": "迟滞图形",
            "settings": "设置",
            "processed": "处理后数据",
        }
    return {
        "response_summary": "Response Summary",
        "response_figures": "Stage Figures",
        "response_overview": "Full Overview",
        "hysteresis_summary": "Hysteresis Summary",
        "run_detail": "Run Detail",
        "hysteresis_figures": "Hysteresis Figures",
        "settings": "Settings",
        "processed": "Processed Data",
    }


def _add_figure_sheet(workbook, sheet_name: str, figures: Iterable[FigureSpec]) -> None:
    figures = list(figures)
    if not figures:
        return
    if sheet_name in workbook.sheetnames:
        del workbook[sheet_name]
    ws = workbook.create_sheet(sheet_name)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 18
    for column in range(2, 13):
        ws.column_dimensions[get_column_letter(column)].width = 12

    row = 1
    for index, (title, image_path) in enumerate(figures, start=1):
        path = Path(image_path)
        if not path.exists():
            continue

        title_cell = ws.cell(row=row, column=1, value=str(title))
        title_cell.font = Font(bold=True, size=12)
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=12)
        ws.row_dimensions[row].height = 22
        row += 1

        image = XLImage(str(path))
        max_width_px = 1180.0
        max_height_px = 720.0
        scale = min(1.0, max_width_px / max(float(image.width), 1.0), max_height_px / max(float(image.height), 1.0))
        image.width = float(image.width) * scale
        image.height = float(image.height) * scale
        image.anchor = f"A{row}"
        ws.add_image(image)

        # Excel's default row height is roughly 20 px. Reserve enough rows so
        # figures never overlap when every response stage is exported.
        rows_for_image = max(20, int(round(float(image.height) / 20.0)) + 3)
        row += rows_for_image
        if index < len(figures):
            row += 1


def export_response_xlsx(
    result: ResponseAnalysisResult,
    path: str | Path,
    include_processed: bool = True,
    stage_figures: Iterable[FigureSpec] | None = None,
    overview_figure: FigureSpec | None = None,
    language: str = "en_US",
) -> Path:
    out = Path(path).with_suffix(".xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    names = _sheet_names(language)

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        # The events table is the complete full-file response result. One row
        # represents one identified response stage/direction event.
        result.events.to_excel(writer, sheet_name=names["response_summary"], index=False)
        _settings_frame(result.settings, language).to_excel(writer, sheet_name=names["settings"], index=False)
        if include_processed:
            result.processed.to_excel(writer, sheet_name=names["processed"], index=False)

    workbook = load_workbook(out)
    for sheet in workbook.worksheets:
        _format_numbers(sheet)
        _autosize(sheet)

    if overview_figure is not None:
        _add_figure_sheet(workbook, names["response_overview"], [overview_figure])
    if stage_figures:
        _add_figure_sheet(workbook, names["response_figures"], stage_figures)

    workbook.save(out)
    return out


def export_hysteresis_xlsx(
    result: HysteresisAnalysisResult,
    path: str | Path,
    include_processed: bool = False,
    figures: Iterable[FigureSpec] | None = None,
    language: str = "en_US",
) -> Path:
    out = Path(path).with_suffix(".xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    names = _sheet_names(language)

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        # Summary and run detail together retain every evaluated current stage,
        # sweep direction and rebound/compression result.
        result.summary.to_excel(writer, sheet_name=names["hysteresis_summary"], index=False)
        result.runs.to_excel(writer, sheet_name=names["run_detail"], index=False)
        _settings_frame(result.settings, language).to_excel(writer, sheet_name=names["settings"], index=False)
        if include_processed:
            result.processed.to_excel(writer, sheet_name=names["processed"], index=False)

    workbook = load_workbook(out)
    for sheet in workbook.worksheets:
        _format_numbers(sheet)
        _autosize(sheet)

    if figures:
        _add_figure_sheet(workbook, names["hysteresis_figures"], figures)

    workbook.save(out)
    return out
