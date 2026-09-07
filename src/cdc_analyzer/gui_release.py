from __future__ import annotations

import html
import sys

from .gui import _qt_imports
from .gui_v05 import _build_gui_classes_v05, _help_html
from .product_info import (
    AUTHOR_DEPARTMENT_ZH,
    AUTHOR_NAME_ZH,
    COMPANY_EN,
    COMPANY_ZH,
    PRODUCT_NAME,
    RELEASE_DATE,
    RELEASE_EDITION_EN,
    RELEASE_EDITION_ZH,
)


def _release_help_html(language: str) -> str:
    base = _help_html(language)
    if language == "zh_CN":
        old_title = "CDC 零位阻尼力分析器 — 专业帮助"
        new_title = f"{PRODUCT_NAME} — 专业帮助"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_ZH)}</b><br>
          {html.escape(COMPANY_EN)}<br>
          编制：{html.escape(AUTHOR_DEPARTMENT_ZH)}　{html.escape(AUTHOR_NAME_ZH)}<br>
          发布日期：{html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_ZH)}
        </div>
        """
    else:
        old_title = "CDC Zero Position Force Analyzer — Professional Help"
        new_title = f"{PRODUCT_NAME} — Professional Help"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_EN)}</b><br>
          {html.escape(COMPANY_ZH)}<br>
          Prepared by: {html.escape(AUTHOR_DEPARTMENT_ZH)} / {html.escape(AUTHOR_NAME_ZH)}<br>
          Release date: {html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_EN)}
        </div>
        """
    updated = base.replace(old_title, new_title)
    marker = f"<h1>{new_title}</h1>"
    return updated.replace(marker, marker + release_box, 1)


def _build_release_gui_classes():
    _, _, _ = _qt_imports()
    BaseMainWindow = _build_gui_classes_v05()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            super().__init__()
            self._apply_release_identity()

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if hasattr(self, "help_browser"):
                self._apply_release_identity()

        def _apply_release_identity(self):
            self.setWindowTitle(PRODUCT_NAME)
            if hasattr(self, "help_browser"):
                self.help_browser.setHtml(_release_help_html(self.language))

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_release_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
