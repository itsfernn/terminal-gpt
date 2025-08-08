

import urwid

from custom_widgets.chat import ChatHistory, EditableChatBubble


class VimKeyHandler(urwid.WidgetWrap):
    MAX_KEY_SEQ_LENGTH = 2
    def __init__(self, chat_history, header=None, footer=None):
        self.chat_history : ChatHistory = chat_history
        self.header = header
        self.footer = footer

        self.frame = urwid.Frame(
            body=chat_history,
            header=header,
            footer=self.footer,
            focus_part='body'
        )

        self.set_insert_mode(self.chat_history.in_insert_mode())

        self.keybinds = {
            ('G',): self.go_to_last_message,
            ('i',): self.enter_insert_mode,
            ('a',): self.enter_insert_mode,
            ('I',): lambda: self.enter_insert_mode("start"),
            ('A',): lambda: self.enter_insert_mode("end"),
            ('j',): self.focus_next_message,
            ('k',): self.focus_previous_message,
            ('l',): self.switch_message_to_user,
            ('h',): self.switch_message_to_assistant,
            ('ctrl up',): self.swap_message_up,
            ('ctrl down',): self.swap_message_down,
            ('o',): self.add_message_above,
            ('O',): self.add_message_below,
            ('c', ): self.clear_focused_message,
            ('d', 'd'): self.delete_focused_message,
            ('g', 'g'): self.go_to_first_message,
        }

        self.key_buffer = []


        super().__init__(self.frame)

    def focus_next_message(self):
        idx = self.chat_history.focus_position +  1
        last_message = self.chat_history.message_list[-1]
        if idx > len(self.chat_history.message_list)-1:
            if last_message.get_content():
                self.chat_history.message_list.append(EditableChatBubble(content="", role="user"))
            self.chat_history.set_focus(len(self.chat_history.message_list) - 1, coming_from='above')
        else:
            self.chat_history.set_focus(idx, coming_from='above')

    def focus_previous_message(self):
        idx = self.chat_history.focus_position - 1
        if idx < 0:
            idx = 0
        self.chat_history.set_focus(idx, coming_from='above')

    def set_insert_mode(self, mode):
        self.insert_mode = mode
        if self.footer is not None:
            mode = "insert" if mode else "normal"
            self.footer.update(mode=mode)

    def keypress(self, size, key):
        # always reset on esc
        if self.insert_mode:
            if key == "esc":
                self.key_buffer.clear()
                self.set_insert_mode(False)
            return super().keypress(size, key)

        self.key_buffer.append(key)
        if self.footer is not None:
            self.footer.update(key_sequence = "".join(self.key_buffer))

        for keybind in self.keybinds:
            if keybind == tuple(self.key_buffer):
                self.keybinds[keybind]()
                self.key_buffer.clear()
                return None
            elif keybind[:len(self.key_buffer)] == tuple(self.key_buffer): 
                # partial match
                return None

        self.key_buffer.clear()
        if self.footer is not None:
            self.footer.update(key_sequence = "".join(self.key_buffer))
        return super().keypress(size, key)

    def enter_insert_mode(self, edit_position=None):
        if self.chat_history.focus is None:
            edit_message = EditableChatBubble(content="", role="user")
            self.chat_history.message_list.append(edit_message)
            self.chat_history.set_focus(len(self.chat_history.message_list) - 1, coming_from='above')
        else:
            edit_message = self.chat_history.focus

        self.set_insert_mode(True)

        assert(isinstance(edit_message, EditableChatBubble))
        if not edit_message.in_insert_mode():
            edit_message.enter_insert_mode(edit_position)



    def delete_focused_message(self):
        try:
            idx = self.chat_history.focus_position
            self.chat_history.delete_message(idx)
        except IndexError:
            pass

    def clear_focused_message(self):
        if self.chat_history.focus is not None:
            assert(isinstance(self.chat_history.focus, EditableChatBubble))
            self.set_insert_mode(True)
            self.chat_history.focus.content = ""
            self.chat_history.focus.enter_insert_mode()

    def go_to_first_message(self):
        try:
            self.chat_history.set_focus(0, coming_from='above')
        except IndexError:
            pass

    def go_to_last_message(self):
        try:
            last_index = len(self.chat_history.message_list) - 1
            self.chat_history.set_focus(last_index, coming_from='above')
        except IndexError:
            pass

    def switch_message_role(self, role):
        current_message = self.chat_history.focus
        if current_message is not None:
            assert(isinstance(current_message, EditableChatBubble))
            current_message.role = role
            current_message.update()

    def switch_message_to_assistant(self):
        self.switch_message_role("assistant")

    def switch_message_to_user(self):
        self.switch_message_role("user")


    def swap_message(self, delta):
        try:
            idx = self.chat_history.focus_position
            new_idx = idx + delta
            if new_idx >= 0:
                message = self.chat_history.message_list[idx]
                prev_message = self.chat_history.message_list[new_idx]
                self.chat_history.message_list[idx] = prev_message
                self.chat_history.message_list[new_idx] = message
                self.chat_history.set_focus(new_idx, coming_from='above')
        except IndexError:
            pass


    def swap_message_up(self):
        self.swap_message(-1)

    def swap_message_down(self):
        self.swap_message(1)


    def add_message(self, index):
        new_message = EditableChatBubble(content="", role="user")
        self.chat_history.message_list.insert(index, new_message)
        self.chat_history.set_focus(index, coming_from='above')
        self.insert_mode = True
        new_message.enter_insert_mode()


    def add_message_above(self):
        if len(self.chat_history.message_list) == 0:
            self.add_message(0)
            return
        else:
            idx = self.chat_history.focus_position
            self.add_message(idx)

    def add_message_below(self):
        if len(self.chat_history.message_list) == 0:
            self.add_message(0)
            return
        else:
            idx = self.chat_history.focus_position + 1
            self.add_message(idx)

