"""Device-independent controls and intersection annotation geometry."""
from PySide6 import QtCore, QtGui, QtWidgets


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(6)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QtCore.QRect(0, 0, width, 0), False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        result = QtCore.QSize()
        for item in self.items:
            result = result.expandedTo(item.minimumSize())
        return result

    def _arrange(self, rect, apply):
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            if item.isEmpty():
                continue
            size = item.sizeHint()
            if x > rect.x() and x + size.width() > rect.right() + 1:
                x, y, height = rect.x(), y + height + self.spacing(), 0
            if apply:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), size))
            x += size.width() + self.spacing()
            height = max(height, size.height())
        return y + height - rect.y()


class IntersectionLabels:
    """Place transparent text above/below points in logical scene pixels.

    Recalculate on zoom/resize. Break dashed guides under text instead of
    covering measured signals with opaque annotation boxes.
    """
    def __init__(self, plot, pg, font, foreground, pen):
        self.plot, self.pg, self.font = plot, pg, font
        self.foreground, self.pen = foreground, pen
        self.labels, self.guides, self.lines = [], [], []
        self.busy = False
        plot.vb.sigResized.connect(self.update)
        plot.vb.sigRangeChanged.connect(self.update)

    def label(self, text, x, y, *, level=False):
        item = self.pg.TextItem(text=text, color=self.foreground, anchor=(0.5, 0.5))
        item.setFont(self.font)
        item.setZValue(20)
        self.plot.addItem(item, ignoreBounds=True)
        self.labels.append((item, float(x), float(y), level))
        return item

    def guide(self, value, *, vertical):
        self.guides.append((float(value), vertical))

    def update(self, *_):
        if self.busy:
            return
        self.busy = True
        try:
            vb = self.plot.vb
            bounds = vb.sceneBoundingRect().adjusted(5, 5, -5, -5)
            if bounds.width() < 50 or bounds.height() < 50:
                return
            rects = []
            for item, x, y, level in self.labels:
                point = vb.mapViewToScene(QtCore.QPointF(x, y))
                width, height = item.boundingRect().width(), item.boundingRect().height()
                cx = point.x() + width / 2 if level else point.x()
                cx = max(bounds.left() + width / 2, min(cx, bounds.right() - width / 2))
                chosen = None
                # First try directly above, then below the intersection. Only
                # increase vertical separation if nearby labels would overlap.
                candidates = [point.y() - 6 - height / 2, point.y() + 6 + height / 2,
                              bounds.top() + height / 2, bounds.bottom() - height / 2]
                for occupied in rects:
                    candidates.extend([occupied.top() - height / 2 - 4,
                                       occupied.bottom() + height / 2 + 4])
                candidates.sort(key=lambda cy: (abs(cy - point.y()), cy > point.y()))
                for cy in candidates:
                    if not level and abs(cy - point.y()) < height / 2 + 5:
                        continue
                    candidate = QtCore.QRectF(cx - width / 2, cy - height / 2, width, height)
                    if bounds.contains(candidate) and not any(candidate.adjusted(-3, -2, 3, 2).intersects(r) for r in rects):
                        chosen = candidate
                        break
                if chosen is None:
                    # Very small manually zoomed view: preserve readability
                    # inside the viewport; the scrollable plot sets a useful
                    # minimum height for the normal 100%/150% layouts.
                    cy = max(bounds.top() + height / 2, min(point.y() - height, bounds.bottom() - height / 2))
                    chosen = QtCore.QRectF(cx - width / 2, cy - height / 2, width, height)
                item.setPos(vb.mapSceneToView(chosen.center()))
                rects.append(chosen)
            self.text_rects = rects
            for line in self.lines:
                self.plot.removeItem(line)
            self.lines.clear()
            xr, yr = vb.viewRange()
            for value, vertical in self.guides:
                lo, hi = yr if vertical else xr
                intervals = [(lo, hi)]
                for rect in rects:
                    a = vb.mapSceneToView(rect.adjusted(-2, -2, 2, 2).topLeft())
                    b = vb.mapSceneToView(rect.adjusted(-2, -2, 2, 2).bottomRight())
                    cross_lo, cross_hi = sorted((a.x(), b.x()) if vertical else (a.y(), b.y()))
                    if not cross_lo <= value <= cross_hi:
                        continue
                    gap_lo, gap_hi = sorted((a.y(), b.y()) if vertical else (a.x(), b.x()))
                    segments = []
                    for left, right in intervals:
                        if gap_hi <= left or gap_lo >= right:
                            segments.append((left, right))
                        else:
                            if left < gap_lo:
                                segments.append((left, gap_lo))
                            if gap_hi < right:
                                segments.append((gap_hi, right))
                    intervals = segments
                for left, right in intervals:
                    line = self.pg.PlotCurveItem(
                        [value, value] if vertical else [left, right],
                        [left, right] if vertical else [value, value], pen=self.pen)
                    self.plot.addItem(line, ignoreBounds=True)
                    self.lines.append(line)
        finally:
            self.busy = False
