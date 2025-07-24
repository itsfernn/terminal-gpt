

import urwid

from custom_widgets.chat import ChatHistory


class VimKeyHandler(urwid.WidgetWrap):
    MAX_KEY_SEQ_LENGTH = 2
    def __init__(self, chat_history, input, header):
        self.chat_history : ChatHistory = chat_history
        self.input = input
        self.header = header
        self.frame = urwid.Frame(
            body=chat_history,
            footer=input,
            header=header,
            focus_part='footer')

        self.keybinds = {
            ('enter',): self.submit_message,
            ('i',): self.insert_mode,
            ('G',): self.go_to_last_message,
            ('ctrl e',): self.edit_focused_in_editor,
            ('q',): self.quit_out,
            ('ctrl c',): self.quit_out,
            ('ctrl d',): self.quit_out,
            ('ctrl right',): self.switch_message_to_user,
            ('ctrl left',): self.switch_message_to_assistant,
            ('ctrl up',): self.swap_message_up,
            ('ctrl down',): self.swap_message_down,
            ('o',): self.add_message_above,
            ('O',): self.add_message_below,
            ('d', 'd'): self.delete_focused_message,
            ('g', 'g'): self.go_to_first_message,
        }

        self.key_buffer = []


        super().__init__(self.frame)

    def keypress(self, size, key):

        # always reset on esc
        if self.frame.focus_position == 'footer':
            if key == "esc":
                self.key_buffer.clear()
                self.frame.focus_position = 'body'
                return None
            return super().keypress(size, key)


        self.key_buffer.append(key)
        self.header.set_keybuffer(self.key_buffer)


        matched = False

        for keybind in self.keybinds:
            if keybind == tuple(self.key_buffer):
                self.keybinds[keybind]()
                self.key_buffer.clear()
                matched = True
                break
            elif keybind[:len(self.key_buffer)] == tuple(self.key_buffer): # partial match
                matched = True
                break

        if not matched:
            self.key_buffer.clear()
            return super().keypress(size, key)

        return None

    def delete_focused_message(self):
        if self.frame.focus_position == 'body':
            idx = self.chat_history.focus_position
            self.chat_history.delete_message(idx)

            if len(self.chat_history.messages) == 0:
                self.frame.focus_position = 'footer'

    def insert_mode(self):
        self.frame.focus_position = 'footer'


    def go_to_first_message(self):
        self.frame.focus_position = 'body'
        self.chat_history.set_focus_first()

    def go_to_last_message(self):
        self.frame.focus_position = 'body'
        self.chat_history.set_focus_last()

    def switch_message_role(self, role):
        idx = self.chat_history.focus_position
        self.chat_history.messages[idx]["role"] = role
        self.chat_history.rebuild()
        # NOTE: Handle this
        #self.loop.draw_screen()

    def switch_message_to_assistant(self):
        self.switch_message_role("assistant")

    def switch_message_to_user(self):
        self.switch_message_role("user")

    def esc(self):
        self.frame.focus_position = 'body'
        self.key_buffer.clear()

    # NOTE: move to app
    def submit_message(self):
        content = self.input.edit.edit_text.strip()
        if not content:
            return
        #asyncio.ensure_future(self.process_input(content))

    # NOTE: maybe use signal or move to app
    def edit_focused_in_editor(self):
        if self.frame.focus_position == 'footer':
            content = self.input.edit.edit_text.strip()
            #new_content = edit_message_in_editor(content)
            #self.input.edit.edit_text = new_content
            #self.loop.screen.clear()
            #self.loop.draw_screen()
            return None
        elif self.frame.focus_position == 'body':
            idx = self.chat_history.focus_position
            #self.edit_message_in_editor(idx)


    def swap_message(self, delta):
        try:
            idx = self.chat_history.focus_position
            new_idx = idx + delta
            if new_idx >= 0:
                message = self.chat_history.messages[idx]
                prev_message = self.chat_history.messages[new_idx]
                self.chat_history.messages[idx] = prev_message
                self.chat_history.messages[new_idx] = message
                self.chat_history.rebuild()
                self.chat_history.set_focus(new_idx, coming_from='above')
        except IndexError:
            return None


    def swap_message_up(self):
        self.swap_message(-1)

    def swap_message_down(self):
        self.swap_message(1)

    # NOTE: again signal posisbly
    def add_message(self, index):
        new_message = {'role': 'user', 'content': ''}
        self.chat_history.messages.insert(index, new_message)
        self.chat_history.rebuild()
        self.chat_history.set_focus(index, coming_from='above')
        #self.edit_message_in_editor(index)


    def add_message_above(self):
        idx = self.chat_history.focus_position
        self.add_message(idx)

    def add_message_below(self):
        idx = self.chat_history.focus_position + 1
        self.add_message(idx)

    def quit_out(self):
        self.chat_history.write_changes()
        raise urwid.ExitMainLoop()
