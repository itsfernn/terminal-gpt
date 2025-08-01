import asyncio
import json
import os
import subprocess
import tempfile

import urwid
from urwid import AsyncioEventLoop

from custom_widgets.chat import ChatHistory, EditableChatBubble
from custom_widgets.model_select import PopupMenu
from custom_widgets.vimkey import VimKeyHandler


def edit_in_editor(content):
    with tempfile.NamedTemporaryFile('w+', delete=False, suffix='.md') as tf:
        tf.write(content)
        tf.flush()
        editor = os.environ.get('EDITOR', 'vi')
        subprocess.call([editor, tf.name])
        tf.seek(0)
        new_content = tf.read().strip()
    os.unlink(tf.name)
    return new_content


class KeyValueText(urwid.WidgetWrap):
    def __init__(self, values={}):
        self.kv_store = values
        self.text = urwid.Text(self.build_string())
        super().__init__(self.text)

    def set_value(self, key, value):
        self.kv_store[key] = value
        self.text.set_text(self.build_string())

    def build_string(self):
        string = ''
        for key, value in self.kv_store.items():
            if string:
                string += " | "
            string += f"{key}: {value}"

        return string


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
            ('focus', 'black', 'white'),
            ('border', 'dark blue', 'default'),
            ('border_focus', 'white', 'default'),
            ('default', 'default', 'default'),
            ('selected', 'black', 'dark blue'),
        ]


        self.model = model
        self.available_models = available_models

        messages = []

        if chat_file is not None:
            self.chat_file = chat_file
            try:
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        self.chat_history = ChatHistory(messages=messages)

        self.header = KeyValueText(values={'model': model})

        self.main = VimKeyHandler(chat_history=self.chat_history, header=self.header)

        self.model_select = PopupMenu(self.available_models, on_select=self.select_model, on_close=self.open_main_view)

        # Main loop with key handler
        self.loop = urwid.MainLoop(
            self.main,
            self.palette,
            unhandled_input=self.handle_input,
            input_filter=self.input_filter,
            event_loop=AsyncioEventLoop(loop=loop)
        )

    def input_filter(self, input_list, raw_input):
        if 'window resize' in input_list:
            self.main.header.set_value("window_size", self.loop.screen.get_cols_rows())
            self.chat_history.rebuild()
        return input_list



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
        widget = self.chat_history.message_list[msg_index]
        content = widget.get_content()
        new_content = edit_in_editor(content)

        widget.content = new_content
        widget.update()

        focus_idx = msg_index
        if 0 <= focus_idx < len(self.chat_history.message_list):
            self.chat_history.set_focus(focus_idx)
        self.loop.screen.clear()
        self.loop.draw_screen()

    def open_main_view(self):
        self.loop.widget = self.main

    def select_model(self, model):
        self.model = model 
        self.header.set_value("model", model)
        self.loop.widget = self.main

    def open_popup(self):
        model_select_overlay = urwid.Overlay(
            top_w=self.model_select,
            bottom_w=self.main,
            align='center',
            width=('pack'),
            valign='middle',
            height=('pack'),
        )
        self.loop.widget = model_select_overlay

    async def get_response(self):
        # add placeholder for assistant
        response_message = EditableChatBubble(content="", role='assistant') 
        self.chat_history.message_list.append(response_message)

        last_index = len(self.chat_history.message_list) - 1
        self.chat_history.set_focus(last_index, "below")

        self.loop.draw_screen()


        # stream response
        # import completion if not already imported async
        if self._completion is None:
            from litellm import completion
            self._completion = completion



        messages = [msg.to_dict() for msg in self.chat_history.message_list[:-1]]
        response = self._completion(model=self.model, messages=messages, stream=True) # type: ignore
        async for chunk in response: # type: ignore
            delta = chunk.choices[0].delta.content
            if delta:
                response_message.content += delta
                response_message.update()
                self.chat_history.set_focus_valign("bottom")
                self.loop.draw_screen()

    def write_changes(self):
        with open(self.chat_file, 'w', encoding='utf-8') as f:
            json.dump(self.chat_history.to_dict(), f, ensure_ascii=False, indent=2)

    def handle_input(self, key):
        if key == "enter":
            asyncio.ensure_future(self.get_response())
            return None

        elif key == 'ctrl e':
            idx = self.main.chat_history.focus_position
            self.edit_message_in_editor(idx)
            return None

        elif key == 'ctrl p':
            self.open_popup()
            return None



    def run(self):
        self.loop.run()
