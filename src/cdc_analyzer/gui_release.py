from __future__ import annotations

import html
import sys
from importlib.resources import files

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

OFFICIAL_WEBSITE = "https://www.faw-tokico.com/"


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
          发布日期：{html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_ZH)}<br>
          公司官网：{html.escape(OFFICIAL_WEBSITE)}
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
          Release date: {html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_EN)}<br>
          Official website: {html.escape(OFFICIAL_WEBSITE)}
        </div>
        """
    updated = base.replace(old_title, new_title)
    marker = f"<h1>{new_title}</h1>"
    return updated.replace(marker, marker + release_box, 1)


def _find_bundled_logo():
    try:
        asset_dir = files("cdc_analyzer").joinpath("assets")
        for name in (
            "faw_tokico_logo.svg",
            "faw_tokico_logo.png",
            "faw_tokico_logo.webp",
            "faw_tokico_logo.jpg",
            "faw_tokico_logo.jpeg",
            "faw_tokico_logo.ico",
        ):
            candidate = asset_dir.joinpath(name)
            if candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    return None


def _build_release_gui_classes():
    QtCore, QtWidgets, _ = _qt_imports()
    from PySide6 import QtGui

    BaseMainWindow = _build_gui_classes_v05()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            # These attributes must exist before BaseMainWindow builds the bilingual UI,
            # because language callbacks are virtual and may reach _apply_release_identity.
            self.brand_frame = None
            self.brand_logo = None
            self.brand_title = None
            self.brand_company = None
            self.brand_release = None
            super().__init__()
            self._insert_brand_header()
            self._apply_release_identity()

        def _insert_brand_header(self):
            splitter = self.centralWidget().findChild(QtWidgets.QSplitter)
            if splitter is None or splitter.count() < 1:
                return
            scroll = splitter.widget(0)
            if not isinstance(scroll, QtWidgets.QScrollArea) or scroll.widget() is None:
                return
            host_layout = scroll.widget().layout()
            if host_layout is None:
                return

            frame = QtWidgets.QFrame()
            frame.setObjectName("brandHeader")
            frame.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
            layout = QtWidgets.QHBoxLayout(frame)
            layout.setContentsMargins(10, 9, 10, 9)
            layout.setSpacing(10)

            logo = QtWidgets.QLabel()
            logo.setMinimumSize(150, 58)
            logo.setMaximumSize(190, 72)
            logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            logo_path = _find_bundled_logo()
            if logo_path:
                pixmap = QtGui.QPixmap(logo_path)
                if not pixmap.isNull():
                    logo.setPixmap(
                        pixmap.scaled(
                            180,
                            68,
                            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    self.setWindowIcon(QtGui.QIcon(pixmap))
                else:
                    logo.setText("FAWER-TOKICO")
            else:
                logo.setText("FAWER-TOKICO")
            layout.addWidget(logo)

            text_box = QtWidgets.QVBoxLayout()
            title = QtWidgets.QLabel(PRODUCT_NAME)
            title_font = title.font()
            title_font.setBold(True)
            title_font.setPointSize(max(11, title_font.pointSize() + 2))
            title.setFont(title_font)
            title.setWordWrap(True)
            company = QtWidgets.QLabel()
            company.setWordWrap(True)
            release = QtWidgets.QLabel()
            release.setWordWrap(True)
            text_box.addWidget(title)
            text_box.addWidget(company)
            text_box.addWidget(release)
            layout.addLayout(text_box, 1)

            host_layout.insertWidget(0, frame)
            self.brand_frame = frame
            self.brand_logo = logo
            self.brand_title = title
            self.brand_company = company
            self.brand_release = release

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if hasattr(self, "help_browser"):
                self._apply_release_identity()

        def _apply_release_identity(self):
            self.setWindowTitle(PRODUCT_NAME)
            if hasattr(self, "help_browser"):
                self.help_browser.setHtml(_release_help_html(self.language))
            if self.brand_title is None:
                return
            self.brand_title.setText(PRODUCT_NAME)
            if self.language == "zh_CN":
                self.brand_company.setText(f"{COMPANY_ZH}\n{COMPANY_EN}")
                self.brand_release.setText(
                    f"编制：{AUTHOR_DEPARTMENT_ZH}  {AUTHOR_NAME_ZH}\n"
                    f"{RELEASE_DATE}  {RELEASE_EDITION_ZH}"
                )
            else:
                self.brand_company.setText(f"{COMPANY_EN}\n{COMPANY_ZH}")
                self.brand_release.setText(
                    f"Prepared by: {AUTHOR_DEPARTMENT_ZH} / {AUTHOR_NAME_ZH}\n"
                    f"{RELEASE_DATE}  {RELEASE_EDITION_EN}"
                )

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
