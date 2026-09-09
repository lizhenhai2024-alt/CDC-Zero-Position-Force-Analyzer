"""High-resolution PNG export helpers for engineering charts."""
from __future__ import annotations

from pathlib import Path


DEFAULT_PNG_EXPORT_PPI = 300
SUPPORTED_PNG_EXPORT_PPI = (150, 300, 600)
_REFERENCE_SCREEN_PPI = 96
_MIN_EXPORT_WIDTH_AT_600_PPI = 5000


def _validated_ppi(ppi: int) -> int:
    value = int(ppi)
    if value not in SUPPORTED_PNG_EXPORT_PPI:
        raise ValueError(f"Unsupported PNG resolution: {value} PPI")
    return value


def export_width_for_ppi(widget_width: int, ppi: int, requested_scale: float = 1.0) -> int:
    """Return a chart width that preserves the on-screen physical size at the selected PPI."""
    resolution = _validated_ppi(ppi)
    base_width = max(int(widget_width), 800)
    ppi_scale = resolution / _REFERENCE_SCREEN_PPI
    return max(
        int(round(_MIN_EXPORT_WIDTH_AT_600_PPI * resolution / 600)),
        int(round(base_width * max(float(requested_scale), ppi_scale))),
    )


def set_png_ppi(path: str | Path, ppi: int = DEFAULT_PNG_EXPORT_PPI) -> Path:
    """Write standard PNG density metadata after PyQtGraph renders the pixels."""
    from PIL import Image

    resolution = _validated_ppi(ppi)
    output = Path(path).with_suffix(".png")
    with Image.open(output) as source:
        image = source.copy()
    image.save(output, format="PNG", dpi=(resolution, resolution))
    return output


def export_plot_widget_png(
    plot_widget,
    path: str | Path,
    scale: float = 1.0,
    ppi: int = DEFAULT_PNG_EXPORT_PPI,
) -> Path:
    """Export a PyQtGraph widget at the selected PPI with sufficient pixels."""
    import pyqtgraph.exporters

    output = Path(path).with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    exporter = pyqtgraph.exporters.ImageExporter(plot_widget.scene())
    exporter.parameters()["width"] = export_width_for_ppi(plot_widget.width(), ppi, scale)
    exporter.export(str(output))
    return set_png_ppi(output, ppi)
