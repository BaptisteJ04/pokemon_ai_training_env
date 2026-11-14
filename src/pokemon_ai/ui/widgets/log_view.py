"""Event and log stream, filterable by type."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pokemon_ai.core.events import AgentEvent, EventType
from pokemon_ai.ui.models.event_table import (
    LOG_TYPE,
    EventFilterModel,
    EventRow,
    EventTableModel,
    describe_payload,
)


class LogView(QWidget):
    def __init__(self, max_rows: int = 5000, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = EventTableModel(max_rows, self)
        self.proxy = EventFilterModel(self)
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        self.filter_button = QToolButton()
        self.filter_button.setText("Shown types")
        self.filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.filter_button)
        self.type_actions: dict[str, QAction] = {}
        for kind in [*(t.value for t in EventType), LOG_TYPE]:
            action = menu.addAction(kind)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(self._update_filter)
            self.type_actions[kind] = action
        self.filter_button.setMenu(menu)
        self.autoscroll = QCheckBox("Auto-scroll")
        self.autoscroll.setChecked(True)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.model.clear)
        self.count = QLabel()

        bar = QHBoxLayout()
        bar.addWidget(self.filter_button)
        bar.addWidget(self.autoscroll)
        bar.addStretch()
        bar.addWidget(self.count)
        bar.addWidget(clear)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.table)

    def add_event(self, event: AgentEvent) -> None:
        details = describe_payload(event.payload)
        self._add(EventRow(event.timestamp, event.event_type.value, details))

    def add_log(self, level: str, message: str, timestamp: float) -> None:
        self._add(EventRow(timestamp, LOG_TYPE, f"[{level}] {message}"))

    def set_type_visible(self, kind: str, visible: bool) -> None:
        self.type_actions[kind].setChecked(visible)

    def visible_rows(self) -> int:
        return self.proxy.rowCount()

    def _add(self, row: EventRow) -> None:
        self.model.add(row)
        self.count.setText(f"{self.proxy.rowCount()}/{self.model.rowCount()} rows")
        if self.autoscroll.isChecked():
            self.table.scrollToBottom()

    def _update_filter(self) -> None:
        hidden = {kind for kind, action in self.type_actions.items() if not action.isChecked()}
        self.proxy.set_hidden(hidden)
        self.count.setText(f"{self.proxy.rowCount()}/{self.model.rowCount()} rows")
