from __future__ import annotations

from . import gui_release as _base_release
from .dynamic_gui_v074 import DynamicPagesController


def main() -> int:
    # gui_release resolves DynamicPagesController when it builds the MainWindow.
    # Override only that dependency so the released V0.5/V0.6 shell and
    # hysteresis workflow remain unchanged.
    _base_release.DynamicPagesController = DynamicPagesController
    return _base_release.main()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
