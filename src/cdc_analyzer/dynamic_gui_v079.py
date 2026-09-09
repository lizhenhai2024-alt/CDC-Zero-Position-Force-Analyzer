from __future__ import annotations

from .dynamic_gui_v078 import DynamicPagesController as _V078DynamicPagesController


class DynamicPagesController(_V078DynamicPagesController):
    """V0.7.9 response-control cleanup.

    The end-average fraction remains an internal engineering parameter fixed at
    2% for the current implementation, but it is no longer exposed in the main
    response toolbar. The project t90 limit stays visible because it drives the
    PASS/FAIL judgement in the result table.
    """

    def _build_response_page(self):
        super()._build_response_page()

        # Keep the existing algorithm parameter for compatibility/export, but
        # remove it from the normal operator interface. Audi uses the specified
        # final-2% mean; BMW currently keeps the same engineering default until
        # its exact F Anfang/F Ende extraction rule is confirmed.
        self.response_end_fraction.setValue(2.0)
        self.response_end_label.hide()
        self.response_end_fraction.hide()

        # Zero means no project acceptance limit. Present that state explicitly
        # instead of the misleading numeric text "0.00 ms".
        self.response_t90_limit.setSpecialValueText(
            self._text("未设置", "Not set")
        )

    def apply_language(self, language: str):
        super().apply_language(language)
        if hasattr(self, "response_end_fraction"):
            self.response_end_fraction.setValue(2.0)
            self.response_end_label.hide()
            self.response_end_fraction.hide()
            self.response_t90_limit.setSpecialValueText(
                self._text("未设置", "Not set")
            )
