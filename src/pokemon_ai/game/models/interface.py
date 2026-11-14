"""State of the game interface (dialogs, menus, cutscenes) as shown on screen."""

from __future__ import annotations

from dataclasses import dataclass

YES_NO = frozenset({"YES", "NO"})


@dataclass(frozen=True, slots=True)
class MenuItem:
    label: str
    row: int  # screen row (in tiles)
    selected: bool


@dataclass(frozen=True, slots=True)
class InterfaceState:
    text: str = ""  # displayed text (empty while walking around)
    waiting_for_input: bool = False  # the arrow: press A or B to continue
    cursor: tuple[int, int] | None = None  # (column, row) of the cursor of an active menu
    menu_items: tuple[MenuItem, ...] = ()
    input_locked: bool = False  # the game ignores the joypad (cutscene, transition)
    walking: bool = False  # a step is in progress

    @property
    def in_menu(self) -> bool:
        return self.cursor is not None

    @property
    def yes_no(self) -> bool:
        return {item.label for item in self.menu_items} == YES_NO

    @property
    def selected(self) -> str | None:
        return next((item.label for item in self.menu_items if item.selected), None)

    @property
    def has_text(self) -> bool:
        return bool(self.text)

    @property
    def controllable(self) -> bool:
        """The player can move: nothing on screen, no lock, no step in progress."""
        return not (self.text or self.input_locked or self.walking)
