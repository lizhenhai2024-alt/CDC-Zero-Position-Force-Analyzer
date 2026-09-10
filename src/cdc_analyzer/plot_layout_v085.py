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

    Recalculate on zoom/resize. Keep dashed guides continuous and place
    transparent labels clear of their guide/intersection.
    """
    def __init__(self, plot, pg, font, foreground, pen):
        self.plot, self.pg, self.font = plot, pg, font
        self.foreground, self.pen = foreground, pen
        self.labels, self.guides, self.lines = [], [], []
        self.placements = {}
        self.busy = False
        plot.vb.sigResized.connect(self.update)
        plot.vb.sigRangeChanged.connect(self.update)

    def label(self, text, x, y, *, level=False, placement="auto"):
        item = self.pg.TextItem(text=text, color=self.foreground, anchor=(0.5, 0.5))
        item.setFont(self.font)
        item.setZValue(20)
        self.plot.addItem(item, ignoreBounds=True)
        self.labels.append((item, float(x), float(y), level))
        self.placements[item] = placement
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
            rect_by_item = {}

            # Level labels share a left column. Lay them out as one ordered
            # stack so collision avoidance can never visually exchange two
            # adjacent thresholds (most noticeably F90 and F100).
            level_entries = []
            for item, x, y, level in self.labels:
                if not level:
                    continue
                point = vb.mapViewToScene(QtCore.QPointF(x, y))
                width = item.boundingRect().width()
                height = item.boundingRect().height()
                left = max(bounds.left(), min(point.x(), bounds.right() - width))
                desired_cy = point.y() - 6 - height / 2
                level_entries.append((point.y(), item, left, width, height, desired_cy))

            ordered_levels = sorted(level_entries, key=lambda entry: entry[0])
            next_top = None
            stacked = []
            for entry in reversed(ordered_levels):
                _guide_y, item, left, width, height, desired_cy = entry
                cy = desired_cy
                if next_top is not None:
                    cy = min(cy, next_top - 4 - height / 2)
                stacked.append([item, left, width, height, cy])
                next_top = cy - height / 2
            stacked.reverse()

            if stacked:
                top = stacked[0][4] - stacked[0][3] / 2
                if top < bounds.top():
                    shift = bounds.top() - top
                    for entry in stacked:
                        entry[4] += shift

            for item, left, width, height, cy in stacked:
                chosen = QtCore.QRectF(left, cy - height / 2, width, height)
                item.setPos(vb.mapSceneToView(chosen.center()))
                rects.append(chosen)
                rect_by_item[item] = chosen

            for item, x, y, level in self.labels:
                if level:
                    continue
                point = vb.mapViewToScene(QtCore.QPointF(x, y))
                width, height = item.boundingRect().width(), item.boundingRect().height()
                placement = self.placements.get(item, "auto")
                if placement.endswith("-left"):
                    x_candidates = [point.x() - width / 2 - 6,
                                    point.x() + width / 2 + 6]
                elif placement.endswith("-right"):
                    x_candidates = [point.x() + width / 2 + 6,
                                    point.x() - width / 2 - 6]
                else:
                    x_candidates = [point.x(), point.x() - width / 2 - 6,
                                    point.x() + width / 2 + 6]
                if not level:
                    for occupied in rects:
                        x_candidates.extend([
                            occupied.left() - width / 2 - 4,
                            occupied.right() + width / 2 + 4,
                        ])
                x_candidates = [
                    max(bounds.left() + width / 2,
                        min(cx, bounds.right() - width / 2))
                    for cx in x_candidates
                ]
                chosen = None
                above = point.y() - 6 - height / 2
                below = point.y() + 6 + height / 2
                if placement.startswith("below"):
                    candidates = [below, above]
                elif placement.startswith("above") or level:
                    candidates = [above, below]
                else:
                    candidates = [above, below]
                for occupied in rects:
                    candidates.extend([occupied.top() - height / 2 - 4,
                                       occupied.bottom() + height / 2 + 4])
                candidates.extend([bounds.top() + height / 2, bounds.bottom() - height / 2])
                for cy in candidates:
                    for cx in x_candidates:
                        if not level and abs(cy - point.y()) < height / 2 + 5:
                            continue
                        candidate = QtCore.QRectF(cx - width / 2, cy - height / 2, width, height)
                        if bounds.contains(candidate) and not any(
                                candidate.adjusted(-3, -2, 3, 2).intersects(r) for r in rects):
                            chosen = candidate
                            break
                    if chosen is not None:
                        break
                if chosen is None:
                    # Very small manually zoomed view: preserve readability
                    # inside the viewport; the scrollable plot sets a useful
                    # minimum height for the normal 100%/150% layouts.
                    cy = max(bounds.top() + height / 2, min(point.y() - height, bounds.bottom() - height / 2))
                    cx = x_candidates[0]
                    chosen = QtCore.QRectF(cx - width / 2, cy - height / 2, width, height)
                item.setPos(vb.mapSceneToView(chosen.center()))
                rects.append(chosen)
                rect_by_item[item] = chosen
            self.text_rects = [rect_by_item[item] for item, *_ in self.labels]
            for line in self.lines:
                self.plot.removeItem(line)
            self.lines.clear()
            xr, yr = vb.viewRange()
            for value, vertical in self.guides:
                line = self.pg.PlotCurveItem(
                    [value, value] if vertical else xr,
                    yr if vertical else [value, value], pen=self.pen)
                self.plot.addItem(line, ignoreBounds=True)
                self.lines.append(line)
        finally:
            self.busy = False
