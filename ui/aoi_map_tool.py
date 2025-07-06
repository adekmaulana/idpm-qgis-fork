from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.core import QgsWkbTypes, QgsPointXY, QgsRectangle
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QKeyEvent


class AoiMapTool(QgsMapToolEmitPoint):
    """
    A custom map tool for drawing a rectangular Area of Interest (AOI).

    Emits a signal with the selected rectangle when the user finishes drawing.
    Handles cancellation via the Escape key.
    """

    # Signal to emit when an AOI rectangle is successfully drawn
    # It passes the QgsRectangle object of the AOI
    aoiSelected = pyqtSignal(QgsRectangle)

    # Signal to emit when the tool is cancelled (e.g., by pressing ESC)
    cancelled = pyqtSignal()

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = None
        self.start_point = None
        self.end_point = None
        self.is_drawing = False

        # Configure the visual style of the rubber band (the rectangle being drawn)
        self._configure_rubber_band()

    def _configure_rubber_band(self):
        """Sets up the visual properties of the drawing rectangle."""
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 128))  # Semi-transparent red
        self.rubber_band.setWidth(2)
        self.rubber_band.setLineStyle(Qt.DashLine)
        self.rubber_band.reset()

    def canvasPressEvent(self, event):
        """Handles the mouse press event to start drawing the rectangle."""
        if event.button() == Qt.LeftButton:
            self.start_point = self.toMapCoordinates(event.pos())
            self.end_point = self.start_point
            self.is_drawing = True

    def canvasMoveEvent(self, event):
        """Handles the mouse move event to update the rectangle as the user drags."""
        if not self.is_drawing:
            return

        self.end_point = self.toMapCoordinates(event.pos())
        self._update_rubber_band()

    def canvasReleaseEvent(self, event):
        """
        Handles the mouse release event to finalize the rectangle and emit the signal.
        """
        if event.button() == Qt.LeftButton and self.is_drawing:
            self.is_drawing = False
            final_rectangle = self.get_rectangle()
            if final_rectangle:
                self.aoiSelected.emit(final_rectangle)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key presses, specifically looking for the Escape key to cancel."""
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()

    def get_rectangle(self) -> QgsRectangle:
        """Constructs a QgsRectangle from the start and end points."""
        if not self.start_point or not self.end_point:
            return None
        return QgsRectangle(self.start_point, self.end_point)

    def _update_rubber_band(self):
        """Updates the rubber band's geometry to show the rectangle being drawn."""
        if not self.is_drawing:
            return

        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        rect = self.get_rectangle()
        if rect:
            self.rubber_band.addPoint(
                QgsPointXY(rect.xMinimum(), rect.yMinimum()), False
            )
            self.rubber_band.addPoint(
                QgsPointXY(rect.xMinimum(), rect.yMaximum()), False
            )
            self.rubber_band.addPoint(
                QgsPointXY(rect.xMaximum(), rect.yMaximum()), False
            )
            self.rubber_band.addPoint(
                QgsPointXY(rect.xMaximum(), rect.yMinimum()), True
            )  # True to close the ring
            self.rubber_band.show()

    def deactivate(self):
        """Called when the tool is deactivated."""
        if self.rubber_band:
            self.rubber_band.reset()
        super().deactivate()
