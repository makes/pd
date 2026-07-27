from textual.widgets import OptionList


class BrowseList(OptionList):
    """OptionList with the vim-ish browsing keys DESIGN.md specifies everywhere lists appear."""

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("ctrl+f", "page_down", "Page down"),
        ("ctrl+d", "half_page_down", "Half page down"),
        ("ctrl+b", "page_up", "Page up"),
        ("ctrl+u", "half_page_up", "Half page up"),
    ]

    def action_half_page_down(self) -> None:
        for _ in range(max(self.size.height // 2, 1)):
            self.action_cursor_down()

    def action_half_page_up(self) -> None:
        for _ in range(max(self.size.height // 2, 1)):
            self.action_cursor_up()
