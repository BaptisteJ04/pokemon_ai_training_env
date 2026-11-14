"""Real-time display of the game, and keyboard input for manual mode.

Keys: arrows; A or X = A button; B or Z = B button; Enter = START; Backspace or Shift = SELECT.
The widget only emits the buttons that are held.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFocusEvent, QImage, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from pokemon_ai.emulator.controls import Button

SCREEN_WIDTH, SCREEN_HEIGHT = 160, 144
KEYS = {
    Qt.Key.Key_Up: Button.UP,
    Qt.Key.Key_Down: Button.DOWN,
    Qt.Key.Key_Left: Button.LEFT,
    Qt.Key.Key_Right: Button.RIGHT,
    Qt.Key.Key_A: Button.A,
    Qt.Key.Key_X: Button.A,
    Qt.Key.Key_B: Button.B,
    Qt.Key.Key_Z: Button.B,
    Qt.Key.Key_Return: Button.START,
    Qt.Key.Key_Enter: Button.START,
    Qt.Key.Key_Backspace: Button.SELECT,
    Qt.Key.Key_Shift: Button.SELECT,
}
KEY_HELP = "Arrows, A/X = A, B/Z = B, Enter = START, Backspace = SELECT"


class GameView(QWidget):
    buttons_changed = Signal(frozenset)

    def __init__(self, scale: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._held: frozenset[Button] = frozenset()
        self.scale = scale
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip(f"Manual mode: click here, then {KEY_HELP}")
        self.frames_shown = 0

    def set_scale(self, scale: int) -> None:
        self.scale = scale
        self.setMinimumSize(SCREEN_WIDTH * scale, SCREEN_HEIGHT * scale)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(SCREEN_WIDTH * self.scale, SCREEN_HEIGHT * self.scale)

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self.frames_shown += 1
        self.update()

    @property
    def held_buttons(self) -> frozenset[Button]:
        return self._held

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        if self._image is not None:
            width, height = SCREEN_WIDTH * self.scale, SCREEN_HEIGHT * self.scale
            left, top = (self.width() - width) // 2, (self.height() - height) // 2
            target = QRect(left, top, width, height)
            # Integer zoom without smoothing: Game Boy pixels stay sharp.
            painter.drawImage(target, self._image)
        if self.hasFocus():
            painter.setPen(QColor(90, 160, 250))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        painter.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        button = KEYS.get(Qt.Key(event.key()))
        if button is None:
            super().keyPressEvent(event)
            return
        if not event.isAutoRepeat():
            self._set_held(self._held | {button})

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        button = KEYS.get(Qt.Key(event.key()))
        if button is None:
            super().keyReleaseEvent(event)
            return
        if not event.isAutoRepeat():
            self._set_held(self._held - {button})

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._set_held(frozenset())  # no key stays stuck
        self.update()
        super().focusOutEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.update()
        super().focusInEvent(event)

    def _set_held(self, buttons: frozenset[Button]) -> None:
        if buttons != self._held:
            self._held = buttons
            self.buttons_changed.emit(buttons)
