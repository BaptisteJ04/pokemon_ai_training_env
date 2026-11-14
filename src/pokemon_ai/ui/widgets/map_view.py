"""Display of the discovered map.

It shows the map where the player is, with tiles colored by type (unknown in gray), the player
and the points of interest. Optional overlay layers, drawn from agent events:
1. cells explored by the last A* search (translucent blue);
2. the chosen path (red) and the destination;
3. the path actually travelled (green).
A double-click on a known walkable tile emits `cell_activated` (go to that tile).
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QMouseEvent,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pokemon_ai.game.models.map import Cell, MapGrid, Position, TileType
from pokemon_ai.game.models.world_map import PoiKind, WorldMap

CELL = 8  # pixels per tile in the scene
TILE_COLORS = {
    TileType.UNKNOWN: (110, 110, 110),
    TileType.WALKABLE: (232, 228, 204),
    TileType.BLOCKED: (60, 60, 60),
    TileType.GRASS: (96, 176, 84),
    TileType.WATER: (72, 124, 220),
    TileType.BUILDING: (150, 90, 60),
    TileType.TRANSITION: (240, 140, 30),
    TileType.INTERACTIVE: (235, 210, 40),
    TileType.LEDGE: (150, 100, 55),
    TileType.CUT_TREE: (30, 110, 45),
}
POI_COLORS = {
    PoiKind.NPC: QColor(210, 40, 200),
    PoiKind.ITEM: QColor(230, 30, 30),
    PoiKind.OBJECT: QColor(120, 80, 200),
    PoiKind.SIGN: QColor(255, 255, 255),
    PoiKind.FIXTURE: QColor(160, 220, 255),
    PoiKind.POKECENTER: QColor(255, 60, 60),
    PoiKind.MART: QColor(60, 120, 255),
    PoiKind.GYM: QColor(255, 200, 0),
}
LAYERS = ("explored", "traveled", "path", "destination")  # from bottom to top
EXPLORED_COLOR = QColor(40, 110, 255, 70)
PATH_COLOR = QColor(220, 0, 0)
TRAVELED_COLOR = QColor(20, 170, 60)
MAX_TRAVELED = 2000  # points kept per map


def grid_image(grid: MapGrid) -> QImage:
    palette = np.array([TILE_COLORS[TileType(i)] for i in range(len(TileType))], dtype=np.uint8)
    pixels = np.ascontiguousarray(palette[grid.tiles].repeat(CELL, 0).repeat(CELL, 1))
    height, width, _ = pixels.shape
    return QImage(pixels.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()


class MapView(QWidget):
    cell_activated = Signal(object)  # Position that was double-clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel("Aucune carte")
        self.follow = QCheckBox("Suivre le joueur")
        self.follow.setChecked(True)
        self.follow.toggled.connect(lambda checked: checked and self._place_player())
        self.scene = QGraphicsScene(self)
        self.view = _ZoomableView(self.scene)
        self.view.double_clicked.connect(self._on_double_click)
        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.follow)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.view)

        self._tiles = QGraphicsPixmapItem()
        self.scene.addItem(self._tiles)
        self._pois = QGraphicsItemGroup()
        self.scene.addItem(self._pois)
        self.layers: dict[str, QGraphicsItemGroup] = {}
        for depth, name in enumerate(LAYERS, start=2):
            group = QGraphicsItemGroup()
            group.setZValue(depth)
            self.scene.addItem(group)
            self.layers[name] = group
        self._player = self.scene.addEllipse(
            QRectF(1, 1, CELL - 2, CELL - 2), QPen(QColor(0, 0, 0)), QBrush(QColor(20, 120, 255))
        )
        self._player.setZValue(10)
        self._player.hide()

        self.world_map = WorldMap()
        self.position: Position | None = None
        self.displayed_map: int | None = None
        self._search: tuple[list[Position], list[Position], Position | None] = ([], [], None)
        self._traveled: dict[int, list[Cell]] = {}

    # --- Data ---

    def set_world_map(self, world_map: WorldMap) -> None:
        self.world_map = world_map
        self._redraw()

    def set_position(self, position: Position) -> None:
        changed_map = self.position is None or position.map_id != self.position.map_id
        self.position = position
        if changed_map:
            self._redraw()
        else:
            self._place_player()

    def show_search(
        self, path: list[Position], expanded: list[Position], destination: Position | None
    ) -> None:
        """Last A* search: explored cells, chosen path and destination."""
        self._search = (path, expanded, destination)
        self._draw_search()

    def add_traveled(self, position: Position) -> None:
        cells = self._traveled.setdefault(position.map_id, [])
        if not cells or cells[-1] != position.cell:
            cells.append(position.cell)
            del cells[:-MAX_TRAVELED]
        if position.map_id == self.displayed_map:
            self._draw_traveled()

    # --- Overlay layers ---

    def set_explored(self, cells: list[Cell]) -> None:
        self._clear_layer("explored")
        brush = QBrush(EXPLORED_COLOR)
        for x, y in cells:
            rect = QRectF(x * CELL, y * CELL, CELL, CELL)
            self.layers["explored"].addToGroup(self.scene.addRect(rect, Qt.PenStyle.NoPen, brush))

    def set_path(self, cells: list[Cell], color: QColor | None = None, layer: str = "path") -> None:
        self._clear_layer(layer)
        if len(cells) < 2:
            return
        path = QPainterPath(_center(cells[0]))
        for previous, cell in pairwise(cells):
            # Farther than a ledge jump (2 tiles): the player came back elsewhere on the map,
            # so the line starts again without joining the two points.
            if abs(cell[0] - previous[0]) + abs(cell[1] - previous[1]) > 2:
                path.moveTo(_center(cell))
            else:
                path.lineTo(_center(cell))
        item = QGraphicsPathItem(path)
        item.setPen(QPen(color or PATH_COLOR, 2))
        self.layers[layer].addToGroup(item)

    def set_destination(self, cell: Cell | None) -> None:
        self._clear_layer("destination")
        if cell is not None:
            rect = QRectF(cell[0] * CELL, cell[1] * CELL, CELL, CELL)
            item = self.scene.addRect(rect, QPen(QColor(255, 0, 0), 2))
            self.layers["destination"].addToGroup(item)

    # --- Drawing ---

    def _redraw(self) -> None:
        map_id = self.position.map_id if self.position is not None else None
        grid = self.world_map.grid(map_id) if map_id is not None else None
        if grid is None:
            self.title.setText("No map discovered")
            self._tiles.setPixmap(QPixmap())
            self._player.hide()
            return
        changed_map = map_id != self.displayed_map
        self.displayed_map = map_id
        if changed_map:  # the layers of the old map no longer apply
            self._draw_search()
            self._draw_traveled()
        self._tiles.setPixmap(QPixmap.fromImage(grid_image(grid)))
        self.scene.setSceneRect(QRectF(0, 0, grid.width * CELL, grid.height * CELL))
        self._draw_pois(grid.map_id)
        self._place_player()
        share = grid.revealed / grid.tiles.size
        self.title.setText(
            f"{grid.name}: {grid.revealed}/{grid.tiles.size} tiles discovered ({share:.0%})"
        )

    def _draw_pois(self, map_id: int) -> None:
        for item in self._pois.childItems():
            self._pois.removeFromGroup(item)
            self.scene.removeItem(item)
        for poi in self.world_map.pois:
            if poi.position.map_id != map_id:
                continue
            x, y = poi.position.x * CELL, poi.position.y * CELL
            rect = QRectF(x + 1, y + 1, CELL - 2, CELL - 2)
            item = self.scene.addRect(rect, QPen(POI_COLORS[poi.kind], 2))
            item.setToolTip(f"{poi.kind.value} {poi.label} ({poi.position.x}, {poi.position.y})")
            self._pois.addToGroup(item)

    def _place_player(self) -> None:
        if self.position is None or self.position.map_id != self.displayed_map:
            self._player.hide()
            return
        self._player.setPos(self.position.x * CELL, self.position.y * CELL)
        self._player.show()
        if self.follow.isChecked():
            self.view.centerOn(self._player)

    def _draw_search(self) -> None:
        path, expanded, destination = self._search
        shown = self.displayed_map
        self.set_explored([p.cell for p in expanded if p.map_id == shown])
        self.set_path([p.cell for p in path if p.map_id == shown])
        self.set_destination(
            destination.cell if destination is not None and destination.map_id == shown else None
        )

    def _draw_traveled(self) -> None:
        cells = self._traveled.get(self.displayed_map, []) if self.displayed_map is not None else []
        self.set_path(cells, TRAVELED_COLOR, layer="traveled")

    def _on_double_click(self, x: float, y: float) -> None:
        grid = self.world_map.grid(self.displayed_map) if self.displayed_map is not None else None
        cell = (int(x // CELL), int(y // CELL))
        if grid is not None and grid.is_passable(*cell):
            self.cell_activated.emit(Position(grid.map_id, *cell))

    def _clear_layer(self, name: str) -> None:
        group = self.layers[name]
        for item in group.childItems():
            group.removeFromGroup(item)
            self.scene.removeItem(item)


class _ZoomableView(QGraphicsView):
    double_clicked = Signal(float, float)  # coordinates in the scene

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setBackgroundBrush(QColor(40, 40, 40))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.scale(3, 3)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        point = self.mapToScene(event.position().toPoint())
        self.double_clicked.emit(point.x(), point.y())


def _center(cell: Cell) -> QPointF:
    return QPointF(cell[0] * CELL + CELL / 2, cell[1] * CELL + CELL / 2)
