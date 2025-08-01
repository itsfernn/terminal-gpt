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

    def __init__(self, content, role):
        text = urwid.Text(content)
        text_attr = urwid.AttrMap(text, role, focus_map='focus')
        text_bubble = urwid.LineBox(text_attr, **self.blocky_border_chars) # type: ignore
        text_bubble_attr = urwid.AttrMap(text_bubble, "border", focus_map='border_focus')

        align = {"user": "right", "assistant": "left"}.get(role, "center")

        max_width = int(urwid.raw_display.Screen().get_cols_rows()[0] * 0.7)
        text_len = max(len(line) for line in content.splitlines()) if content else 0


        if text_len <= max_width:
            padded_text_bubble = urwid.Padding(text_bubble_attr, align=align, width="clip") # type: ignore
        else:
            padded_text_bubble = urwid.Padding(text_bubble_attr, align=align, width=('relative', 70)) # type: ignore

        super().__init__(padded_text_bubble)

    def selectable(self):
        return True

class ChatEdit(urwid.WidgetWrap):
    def __init__(self,content, role):
        align = {"user": "right", "assistant": "left"}.get(role, "center")

        self.edit = urwid.Edit("> ", multiline=True)
        self.edit.set_edit_text(content)

        line_edit = urwid.LineBox(self.edit)
        input = urwid.Padding(line_edit, align=align, width=('relative', 70)) # type: ignore
        super().__init__(input)

    def selectable(self):
        return True

class EditableChatBubble(urwid.WidgetPlaceholder):
    def __init__(self, content, role):
        self.content = content
        self.role = role
        self.chat_bubble = ChatBubble(content, role)
        self.last_edit_position = 0
        super().__init__(self.chat_bubble) # type: ignore

    def enter_insert_mode(self, edit_pos=None):
        if not isinstance(self.original_widget, ChatEdit):
            self.original_widget = ChatEdit(self.content, self.role)
            if edit_pos == "start":
                self.original_widget.edit.set_edit_pos(0)
            elif edit_pos == "end":
                pos = len(self.original_widget.edit.edit_text)
                self.original_widget.edit.set_edit_pos(pos)
            else:
                self.original_widget.edit.set_edit_pos(self.last_edit_position)

    def leave_insert_mode(self):
        if isinstance(self.original_widget, ChatEdit):
            self.content = self.original_widget.edit.edit_text
            self.last_edit_position = self.original_widget.edit.edit_pos
            self.original_widget = ChatBubble(self.content, self.role)

    def in_insert_mode(self):
        return isinstance(self.original_widget, ChatEdit)

    def update(self):
        cls = type(self.original_widget)
        self.original_widget = cls(self.content, self.role)

    def selectable(self):
        return True

    def get_content(self):
        if isinstance(self.original_widget, ChatEdit):
            return self.original_widget.edit.edit_text
        else:
            return self.content

    def to_dict(self):
        return {
                'content':self.get_content(),
                'role': self.role
        }


class ChatHistory(urwid.ListBox):
    def __init__(self, messages=None):
        if messages is None or len(messages) == 0:
            first_message = EditableChatBubble(content="", role="user")
            self.message_list = urwid.SimpleListWalker([first_message])
            first_message.enter_insert_mode(edit_pos="start")
        else:
            self.message_list = urwid.SimpleListWalker(self._build_message_widgets(messages))
        super().__init__(self.message_list)  # Initialize ListBox before using its methods

        last_index = len(self.message_list) - 1
        self.set_focus(last_index)

    def set_focus(self, position, coming_from=None):
        try:
            super().set_focus(position, coming_from)
        except IndexError:
            pass

    def _build_message_widgets(self, messages):
        widgets = []
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content')
            chat_bubble = EditableChatBubble(content=content, role=role)
            widgets.append(chat_bubble)
        return widgets

    def to_dict(self):
        return [msg.to_dict for msg in self.message_list]

    def rebuild(self):
        for message in self.message_list:
            message.update()

    def delete_message(self, index):
        if 0 <= index < len(self.message_list):
            del self.message_list[index]

            new_index = min(index, len(self.message_list))
            self.set_focus(new_index, "below")

    def keypress(self, size, key):
        if self.focus is not None:
            assert(isinstance(self.focus, EditableChatBubble))
            if self.focus.in_insert_mode():
                if key == 'esc':
                    self.focus.leave_insert_mode()
                    return None
                else:
                    return self.focus.keypress(size, key)
            else:
                if key == 'J':
                    return super().keypress(size, 'down')
                elif key == 'K':
                    return super().keypress(size, 'up')
                elif key == 'j':
                    self.set_focus(self.focus_position + 1, coming_from='above')
                elif key == 'k':
                    self.set_focus(self.focus_position -1, coming_from='below')

        return super().keypress(size, key)
