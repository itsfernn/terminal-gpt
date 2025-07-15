import asyncio
import json
import os
import subprocess
import tempfile

import urwid
from urwid import AsyncioEventLoop


def edit_message_in_editor(content):
    with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.md') as tf:
        tf.write(content)
        tf.flush()
        editor = os.environ.get('EDITOR', 'vi')
        subprocess.call([editor, tf.name])
        tf.seek(0)
        new_content = tf.read().strip()
    os.unlink(tf.name)
    return new_content

class PopupMenu(urwid.WidgetWrap):
    def __init__(self, models, on_select, on_close):
        self.models = models
        self.on_select = on_select
        self.on_close = on_close

        # Build a ListBox of Buttons
        buttons = [
            urwid.AttrMap(urwid.Button(m, self.item_chosen), None, focus_map='reversed')
            for m in models
        ]
        self.menu = urwid.ListBox(urwid.SimpleFocusListWalker(buttons))

        # Put it in a LineBox for a border/title
        frame = urwid.LineBox(self.menu, title="Select a Model")

        # Initialize the WidgetWrap with that outer frame
        super().__init__(frame)

    def item_chosen(self, button, *args):
        self.on_select(button.get_label())

    def keypress(self, size, key):
        # j/k → down/up in the ListBox
        if key == 'j':
            return self.menu.keypress(size, 'down')  # type: ignore
        elif key == 'k':
            return self.menu.keypress(size, 'up')   # type: ignore
        elif key in ('q', 'esc'):
            # q/esc → close the popup
            self.on_close()
            return None
        # let Enter and others flow through: buttons handle Enter themselves
        return super().keypress(size, key)

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
    def __init__(self, messages):
        self.messages = messages
        self.message_list = urwid.SimpleListWalker(self._build_message_widgets())
        super().__init__(self.message_list)

    def _build_message_widgets(self):
        widgets = []
        for msg in self.messages:
            role = msg.get('role')
            text = msg.get('content')

            chat_bubble = ChatBubble(text, role)
            widgets.append(chat_bubble)
        return widgets

    def set_messages(self, messages):
        self.messages = messages
        self.message_list[:] = self._build_message_widgets()

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
            self.set_messages(self.messages)
            if len(self.messages) > 0:
                self.set_focus(max(0, index - 1), coming_from='below')

    def keypress(self, size, key):
        pass

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
        elif key == 'ctrl h':
            return key
        elif key == 'ctrl l':
            return key
        return super().keypress(size, key)

class Input(urwid.WidgetWrap):
    def __init__(self):
        self.prefix = "> "
        self.edit = urwid.Edit(self.prefix, multiline=True)
        self.input_box = urwid.LineBox(self.edit)

        super().__init__(self.input_box)


    def selectable(self):
        return True

    def keypress(self, size, key):
        return self.edit.keypress(size, key)




class ChatApp:
    def __init__(self, chat_file, model, available_models):
        # Color palette: user, assistant messages, focus highlight, footer
        self._completion = None
        self.key_seq = ''
        loop = asyncio.get_event_loop()
        loop.call_soon(self._schedule_preload)


        self.palette = [
            ('user', 'black', 'dark blue'),
            ('assistant', 'black', 'dark blue'),
            ('footer', 'default', 'default'),
            ('border', 'dark blue', 'default'),
            ('focus', 'black', 'white'),
            ('border_focus', 'white', 'default'),
        ]


        self.model = model
        self.available_models = available_models
        self.chat_file = chat_file

        try:
            with open(self.chat_file, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self.messages = []



        self.input = Input()
        self.chat_history = ChatHistory(self.messages)
        self.header = urwid.Text(("header", f"Model: {self.model}"))

        self.frame = urwid.Frame(
            body=self.chat_history,
            footer=self.input,
            header=self.header,
        )

        # Main loop with key handler
        self.loop = urwid.MainLoop(
            self.frame,
            self.palette,
            unhandled_input=self.handle_input,
            event_loop=AsyncioEventLoop(loop=loop)
        )


        # Auto-focus on footer on launch
        self.frame.focus_position = 'footer'
        self.chat_history.set_focus_last()

    def selectable(self):
        return True

    def _schedule_preload(self):
        """
        Import litellm.completion in executor to warm up module on startup
        """
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self._preload_completion)

    def _preload_completion(self):
        """
        Blocking import in thread, caches module for later use
        """
        from litellm import completion
        self._completion = completion

    def save_messages(self):
        with open(self.chat_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)


    def edit_message_in_editor(self, msg_index):
        with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.md') as tf:
            tf.write(self.messages[msg_index]['content'])
            tf.flush()
            editor = os.environ.get('EDITOR', 'vi')
            subprocess.call([editor, tf.name])
            tf.seek(0)
            new_content = tf.read().strip()
        os.unlink(tf.name)

        self.messages[msg_index]['content'] = new_content

        self.save_messages() # save changes to file
        self.chat_history.set_messages(self.messages) # update chat history

        focus_idx = msg_index
        if 0 <= focus_idx < len(self.chat_history.message_list):
            self.chat_history.set_focus(focus_idx)
        self.loop.screen.clear()
        self.loop.draw_screen()

    def open_popup(self):
        def on_close():
            self.loop.widget = self.frame
        def on_select(choice):
            self.model = choice
            self.header.set_text(("header", f"Model: {self.model}"))
            self.loop.widget = self.frame

        menu = PopupMenu(self.available_models, on_select, on_close)
        self.overlay = urwid.Overlay(
            top_w=menu,
            bottom_w=self.frame,
            align='center',
            width=('relative', 40),
            valign='middle',
            height=('relative', 40)
        )
        self.loop.widget = self.overlay

    async def process_input(self, content):
        # add user message
        self.messages.append({'role':'user','content':content})
        self.save_messages()
        # add placeholder for assistant
        self.messages.append({'role':'assistant','content':''})
        self.chat_history.set_messages(self.messages)
        self.chat_history.set_focus_last()
        self.loop.draw_screen()


        # stream response
        # import completion if not already imported async
        if self._completion is None:
            from litellm import completion
            self._completion = completion

        response = self._completion(model=self.model, messages=self.messages[:-1], stream=True) # type: ignore
        async for chunk in response: # type: ignore
            delta = chunk.choices[0].delta.content
            if delta:
                self.messages[-1]['content'] += delta
                self.chat_history.set_messages(self.messages)
                #self.chat_history.set_focus_valign('bottom')
                self.loop.draw_screen()
        # final save
        self.save_messages()


    def handle_input(self, key):
        def delete_focused_message():
            if self.frame.focus_position == 'body':
                idx = self.chat_history.focus_position
                try:
                    del self.messages[idx]
                except IndexError:
                    return
                self.chat_history.set_messages(self.messages)
                if len(self.messages) == 0:
                    self.frame.focus_position = 'footer'
                    return
                self.save_messages()


        def insert_mode():
            self.frame.focus_position = 'footer'


        def go_to_first_message():
            self.chat_history.set_focus_first()
            self.frame.focus_position = 'body'

        def go_to_last_message():
            self.chat_history.set_focus_last()
            self.frame.focus_position = 'body'
            
        def switch_message_role(role):
            idx = self.chat_history.focus_position
            self.messages[idx]["role"] = role
            self.save_messages()
            self.chat_history.set_messages(self.messages)
            self.loop.draw_screen()

        def switch_message_to_assistant():
            switch_message_role("assistant")

        def switch_message_to_user():
            switch_message_role("user")

        def esc():
            self.frame.focus_position = 'body'
            self.key_seq = ''

        def submit_message():
            content = self.input.edit.edit_text.strip()
            if not content:
                return
            asyncio.ensure_future(self.process_input(content))

        def edit_focused_in_editor():
            if self.frame.focus_position == 'footer':
                content = self.input.edit.edit_text.strip()
                new_content = edit_message_in_editor(content)
                self.input.edit.edit_text = new_content
                self.loop.screen.clear()
                self.loop.draw_screen()
                return None
            elif self.frame.focus_position == 'body':
                idx = self.chat_history.focus_position
                self.edit_message_in_editor(idx)


        def open_model_selection():
            self.open_popup()

        def quit_out():
            self.save_messages()
            raise urwid.ExitMainLoop()

        def swap_message(delta):
            try:
                idx = self.chat_history.focus_position
                new_idx = idx + delta
                if new_idx >= 0:
                    message = self.messages[idx]
                    prev_message = self.messages[new_idx]
                    self.messages[idx] = prev_message
                    self.messages[new_idx] = message
                    self.chat_history.set_messages(self.messages)
                    self.chat_history.set_focus(new_idx, coming_from='above')
                    self.save_messages()
            except IndexError:
                return None


        def swap_message_up():
            swap_message(-1)

        def swap_message_down():
            swap_message(1)

        def overlay():
            overlay = urwid.Overlay(top_w=Input(),
                                    bottom_w=self.frame,
                                    align='center',
                                    width=('relative', 40),
                                    valign='middle',
                                    height=('relative', 40))
            self.loop.widget = overlay

        def add_message(index):
            new_message = {'role': 'user', 'content': ''}
            self.messages.insert(index, new_message)
            self.chat_history.set_messages(self.messages)
            self.chat_history.set_focus(index, coming_from='above')
            self.edit_message_in_editor(index)


        def add_message_above():
            idx = self.chat_history.focus_position
            add_message(idx)

        def add_message_below():
            idx = self.chat_history.focus_position + 1
            add_message(idx)



        key_maps = {
            'enter': submit_message,
            'ctrl s': submit_message,
            'i': insert_mode,
            'G': go_to_last_message,
            'esc': esc,
            'ctrl p': open_model_selection,
            'ctrl e': edit_focused_in_editor,
            'q': quit_out,
            'ctrl c': quit_out,
            'ctrl d': quit_out,
            'ctrl right': switch_message_to_user,
            'ctrl left': switch_message_to_assistant,
            'ctrl up': swap_message_up,
            'ctrl down': swap_message_down,
            'o': add_message_above,
            'O': add_message_below,
        }

        key_sequences = {
            'dd': delete_focused_message,
            'gg': go_to_first_message,
        }


        if isinstance(key, str):
            self.key_seq += key
        # set header to key pressed DEBUG:
        self.header.set_text(("header", f"Model: {self.model} | Key: {key} | Key Seq: {self.key_seq}"))

        action = key_maps.get(self.key_seq, None)
        if action:
            if callable(action):
                action()
                self.key_seq = ''
                self.header.set_text(("header", f"Model: {self.model} | Key: {key} | Key Seq: {self.key_seq}"))

        action = key_sequences.get(self.key_seq, None)
        if action:
            if callable(action):
                action()
                self.key_seq = ''
                self.header.set_text(("header", f"Model: {self.model} | Key: {key} | Key Seq: {self.key_seq}"))

        if len(self.key_seq) > 5:
            self.key_seq = ''

        if key == 'esc':
            esc()
            return None
        if key == "window resize":
            self.chat_history.set_messages(self.messages) # rebuild message widgets (for relative max width of message bubbles)
        #elif key == 'd':
        #    if self.last_key == 'd':
        #        # delete the focused message
        #        idx = self.chat_history.focus_position
        #        if 0 <= idx < len(self.chat_history.message_list):
        #            del self.messages[idx]
        #            self.chat_history.set_messages(self.messages)
        #            self.save_messages()
        #            if len( self.messages) == 0:
        #                self.frame.focus_position = 'footer'
        #                return 
        #            self.chat_history.set_focus(max(0, idx - 1), coming_from='below')
        #        self.last_key = None
        #        return
        #    self.last_key = 'd'

    def run(self):
        try:
            self.loop.run()
        except KeyboardInterrupt:
            self.exit()

    def exit(self):
        self.save_messages()
        raise urwid.ExitMainLoop()


