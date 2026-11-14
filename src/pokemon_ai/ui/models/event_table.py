"""Qt model of the event stream: one row per event, with a maximum number of rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)

LOG_TYPE = "LOG"  # messages of the logging module, mixed with the events
COLUMNS = ("Time", "Type", "Details")

type Index = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True, slots=True)
class EventRow:
    timestamp: float
    kind: str  # event type, or LOG
    details: str


def describe_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(", ", ": "))


class EventTableModel(QAbstractTableModel):
    def __init__(self, max_rows: int = 5000, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.max_rows = max_rows
        self.rows: list[EventRow] = []

    def add(self, row: EventRow) -> None:
        if len(self.rows) >= self.max_rows:
            overflow = len(self.rows) - self.max_rows + 1
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self.rows[:overflow]
            self.endRemoveRows()
        self.beginInsertRows(QModelIndex(), len(self.rows), len(self.rows))
        self.rows.append(row)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.rows.clear()
        self.endResetModel()

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        row = self.rows[index.row()]
        if index.column() == 0:
            return datetime.fromtimestamp(row.timestamp).strftime("%H:%M:%S.%f")[:-3]
        if index.column() == 1:
            return row.kind
        return row.details

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None


class EventFilterModel(QSortFilterProxyModel):
    """Only shows the checked types."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.hidden: set[str] = set()

    def set_hidden(self, hidden: set[str]) -> None:
        self.beginFilterChange()
        self.hidden = set(hidden)
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: Index) -> bool:
        model = self.sourceModel()
        assert isinstance(model, EventTableModel)
        return model.rows[source_row].kind not in self.hidden
