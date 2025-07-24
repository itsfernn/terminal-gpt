
import json

import urwid


class ChatBubble(urwid.WidgetWrap):
    blocky_border_chars = {
        "tlcorner": "▄",  # Top-left corner
        "tline":    "▄",  # Top edge
        "trcorner": "▄",  # Top-right corner
        "lline":    "█ ",  # Left edge
        "rline":    "█ ",  # Right edge
        "blcorner": "▀",  # Bottom-left corner
        "bline":    "▀",  # Bottom edge
        "brcorner": "▀",  # Bottom-right corner
    }
    def __init__(self, text, role):
        self.text = urwid.Text(text)
        self.text_attr = urwid.AttrMap(self.text, role, focus_map='focus')
        self.text_bubble = urwid.LineBox(self.text_attr, **self.blocky_border_chars) # type: ignore
        self.text_bubble_attr = urwid.AttrMap(self.text_bubble, "border", focus_map='border_focus')

        max_width = int(urwid.raw_display.Screen().get_cols_rows()[0] * 0.7)
        text_len = max(len(line) for line in text.splitlines()) if text else 0 #
        align = {"user": "right", "assistant": "left"}.get(role, "center")

        if text_len <= max_width:
            self.padded_text_bubble = urwid.Padding(self.text_bubble_attr, align=align, width="clip") # type: ignore
        else:
            self.padded_text_bubble = urwid.Padding(self.text_bubble_attr, align=align, width=('relative', 70)) # type: ignore

        super().__init__(self.padded_text_bubble)


    def selectable(self) -> bool:
        return True

class ChatHistory(urwid.ListBox):
    def __init__(self, chat_file=None, messages=None):
        self.messages = messages or []

        if chat_file is not None:
            self.chat_file = chat_file
            try:
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.messages = []

        self.message_list = urwid.SimpleListWalker(self._build_message_widgets())
        super().__init__(self.message_list)  # Initialize ListBox before using its methods
        self.set_focus_last()

    def _build_message_widgets(self):
        widgets = []
        for msg in self.messages:
            role = msg.get('role')
            text = msg.get('content')
            chat_bubble = ChatBubble(text, role)
            widgets.append(chat_bubble)
        return widgets

    def write_changes(self):
        with open(self.chat_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def rebuild(self):
        self.message_list[:] = self._build_message_widgets()


    def set_focus_last(self):
        try:
            last_index = len(self.message_list) - 1
            if last_index > 0:
                self.set_focus(last_index, coming_from='above')
        except IndexError:
            return None

    def set_focus_first(self):
        try:
            if len(self.message_list) > 0:
                self.set_focus(0, coming_from='above')
        except IndexError:
            return None

    def delete_message(self, index):
        if 0 <= index < len(self.message_list):
            del self.messages[index]
            self.rebuild()

    def keypress(self, size, key):
        if key == 'J':
            return super().keypress(size, 'down')
        elif key == 'K':
            return super().keypress(size, 'up')
        elif key == 'j':
            try:
                self.set_focus(self.focus_position + 1, coming_from='above')
                return None
            except Exception:
                return None
        elif key == 'k':
            try:
                self.set_focus(self.focus_position -1, coming_from='below')
                return None
            except Exception:
                return None

        return super().keypress(size, key)
