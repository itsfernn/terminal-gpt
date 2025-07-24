import asyncio
import os
import subprocess
import tempfile

import urwid
from urwid import AsyncioEventLoop

from custom_widgets.chat import ChatHistory
from custom_widgets.model_select import PopupMenu
from custom_widgets.vimkey import VimKeyHandler


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


class CustomHeader(urwid.WidgetWrap):
    def __init__(self, model):
        self.model = model
        self.keybuffer = None
        self.widget = urwid.Text(("header", f"Model: {self.model} | Key: None | Key Buffer: []"))
        super().__init__(self.widget)

    def set_keybuffer(self, keybuffer):
        self.keybuffer = keybuffer
        self.update()

    def set_model(self, model):
        self.model = model
        self.update()

    def update(self):
        string =  ''
        if self.model is not None:
            string = f"Model: {self.model}"

        if self.keybuffer is not None:
            if string:
                string += " | "
            string += f"Key Buffer: {self.keybuffer}"

        self.widget.set_text(("header", string))


class Input(urwid.WidgetWrap):
    def __init__(self):
        self.prefix = "> "
        self.edit = urwid.Edit(self.prefix, multiline=True)
        self.input_box = urwid.LineBox(self.edit)

        super().__init__(self.input_box)


    def selectable(self):
        return True

    # NOTE: I belive this can be removed
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


        self.input = Input()
        self.chat_history = ChatHistory(chat_file=chat_file)
        self.header = CustomHeader(model=self.model)

        self.main = VimKeyHandler(chat_history=self.chat_history, input=self.input, header=self.header)

        self.model_select = PopupMenu(self.available_models, on_select=self.select_model, on_close=self.open_main_view)
        self.model_selet_overlay = urwid.Overlay( top_w=self.model_select, bottom_w=self.main, align='center', width=('relative', 40), valign='middle', height=('relative', 40))

        # Main loop with key handler
        self.loop = urwid.MainLoop(
            self.main,
            self.palette,
            unhandled_input=self.handle_input,
            event_loop=AsyncioEventLoop(loop=loop)
        )

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

    def edit_message_in_editor(self, msg_index):
        with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.md') as tf:
            tf.write(self.chat_history.messages[msg_index]['content'])
            tf.flush()
            editor = os.environ.get('EDITOR', 'vi')
            subprocess.call([editor, tf.name])
            tf.seek(0)
            new_content = tf.read().strip()
        os.unlink(tf.name)

        self.chat_history.messages[msg_index]['content'] = new_content
        self.chat_history.rebuild()

        focus_idx = msg_index
        if 0 <= focus_idx < len(self.chat_history.message_list):
            self.chat_history.set_focus(focus_idx)
        self.loop.screen.clear()
        self.loop.draw_screen()

    def open_main_view(self):
        self.loop.widget = self.main

    def select_model(self, model):
        self.model = model 

    def open_popup(self):
        self.loop.widget = self.model_selet_overlay

    async def process_input(self, content):
        # add user message
        self.chat_history.messages.append({'role':'user','content':content})


        # add placeholder for assistant
        self.chat_history.messages.append({'role':'assistant','content':''})
        self.chat_history.rebuild()
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
                self.chat_history.messages[-1]['content'] += delta
                self.chat_history.rebuild()
                #self.chat_history.set_focus_valign('bottom')
                self.loop.draw_screen()

    def handle_input(self, key):
        if key == "window resize":
            self.chat_history.rebuild()

    def run(self):
        self.loop.run()
