import asyncio
import json
import os
import subprocess
import tempfile

import urwid
from urwid import AsyncioEventLoop


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

class ChatApp:
    def __init__(self, chat_file, model, available_models):
        # Color palette: user, assistant messages, focus highlight, footer
        self._completion = None
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

        self.load_messages()

        # Build message widgets based on history
        self.message_list = urwid.SimpleListWalker(self.build_message_widgets())
        self.listbox = urwid.ListBox(self.message_list)

        # Input field with prompt indicator
        self.input_edit = urwid.Edit("> ", multiline=False)
        bubble = urwid.LineBox(self.input_edit, title_align='center')

        self.footer = urwid.AttrWrap(bubble, 'footer', focus_attr='focus')
        self.header = urwid.Text(("header", f"Model: {self.model}"))

        # Frame layout: body (chat) and footer (input)
        self.frame = urwid.Frame(
            body=urwid.Padding(self.listbox, left=1, right=1),
            footer=self.footer,
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

        # Auto-scroll to bottom of chat
        last_idx = self._last_message_index()
        if last_idx is not None:
            self.listbox.set_focus(last_idx, coming_from='above')

        # For vim-style 'gg' detection
        self.last_key = None

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

    def load_messages(self):
        try:
            with open(self.chat_file, 'r', encoding='utf-8') as f:
                self.messages = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            self.messages = []

    def save_messages(self):
        with open(self.chat_file, 'w', encoding='utf-8') as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def build_message_widgets(self):
        widgets = []
        for msg in self.messages:
            role = msg.get('role')
            text = msg.get('content')


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

            align = {"user": "right", "assistant": "left"}.get(role, "center")


            # Render message bubble
            txt = urwid.Text(text)
            txt = urwid.AttrMap(txt, role, focus_map='focus')
            bubble = urwid.LineBox(txt, **blocky_border_chars) # type: ignore
            bubble = urwid.AttrMap(bubble, "border", focus_map='border_focus')

            max_width = int(urwid.raw_display.Screen().get_cols_rows()[0] * 0.7)
            text_len = max(len(line) for line in text.splitlines()) if text else 0 #

            if text_len <= max_width:
                padded = urwid.Padding(bubble, align=align, width="clip") # type: ignore
            else:
                padded = urwid.Padding(bubble, align=align, width=('relative', 70)) # type: ignore

            widgets.append(padded)
        return widgets

    def refresh_messages(self):
        self.message_list[:] = self.build_message_widgets()

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
        self.save_messages()
        self.refresh_messages()

        focus_idx = msg_index
        if 0 <= focus_idx < len(self.message_list):
            self.listbox.set_focus(focus_idx)
        self.loop.screen.clear()
        self.loop.draw_screen()

    def open_popup(self):
        def on_close():
            self.loop.widget = self.frame
        def on_select(self, choice):
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
        from litellm import completion
        # add user message
        self.messages.append({'role':'user','content':content})
        self.save_messages()
        self.refresh_messages()
        self.loop.draw_screen()
        last = self._last_message_index()
        if last is not None:
            self.listbox.set_focus(last, coming_from='above')

        # add placeholder for assistant
        self.messages.append({'role':'assistant','content':''})
        self.save_messages()
        self.refresh_messages()
        self.loop.draw_screen()
        last = self._last_message_index()
        if last is not None:
            self.listbox.set_focus(last, coming_from='above')

        # stream response
        assistant_buffer = ''
        async for chunk in completion(model=self.model, messages=self.messages[:-1], stream=True):  # type: ignore
            delta = chunk['choices'][0]['delta']['content']
            if delta:
                assistant_buffer += delta
                self.messages[-1]['content'] = assistant_buffer
                self.refresh_messages()
                self.listbox.set_focus_valign('bottom')
                self.loop.draw_screen()
        # final save
        self.save_messages()
        if last is not None:
            self.listbox.set_focus(last, coming_from='above')

    def handle_input(self, key):
        if key == 'enter':
            content = self.input_edit.edit_text.strip()
            if not content:
                return
            self.input_edit.edit_text = ''
            asyncio.ensure_future(self.process_input(content))
        elif key == 'esc':
            self.frame.focus_position = 'body'
        elif key == "window resize":
            self.refresh_messages()
        elif key == 'ctrl p':
            self.open_popup()
        elif key == 'c':
            idx = self.listbox.focus_position
            self.edit_message_in_editor(idx)

        # vim-style and exit logic (as before)
        elif key == 'j':
            self._nav_step(1)
        elif key == 'k':
            self._nav_step(-1)
        elif key == 'G':
            last = self._last_message_index()
            if last is not None:
                self.listbox.set_focus(last, coming_from='below')
        elif key == 'd':
            if self.last_key == 'd':
                # delete the focused message
                idx = self.listbox.focus_position
                if 0 <= idx < len(self.message_list):
                    del self.messages[idx]
                    self.save_messages()
                    self.refresh_messages()
                    if len( self.messages) == 0:
                        self.frame.focus_position = 'footer'
                        return 
                    self.listbox.set_focus(max(0, idx - 1), coming_from='below')
                self.last_key = None
                return
            self.last_key = 'd'
        elif key == 'g':
            if self.last_key == 'g':
                self.listbox.set_focus(0, coming_from='above')
                self.last_key = None
                return
            self.last_key = 'g'
        elif key in ('i', 'a'):
            last = self._last_message_index()
            if last:
                self.listbox.set_focus(last, coming_from='below')
            self.frame.focus_position = 'footer'
        elif key in ('ctrl c', 'ctrl d'):
            raise urwid.ExitMainLoop()
        else:
            self.last_key = None

    def _nav_step(self, step):
        coming_from = "below" if step > 0 else "above"
        idx = self.listbox.focus_position + step
        if 0 <= idx < len(self.message_list):
            self.listbox.set_focus(idx, coming_from=coming_from)
        elif idx < 0:
            self.listbox.set_focus(0)

    def _last_message_index(self):
        count = len(self.message_list)
        return count - 1 if count > 0 else None

    def _first_message_index(self):
        return 0 if self.message_list else None

    def run(self):
        self.loop.run()
