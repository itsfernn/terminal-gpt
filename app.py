import json
import os
import subprocess
import tempfile
import threading

import urwid

from custom_widgets.chat import ChatHistory, EditableChatBubble
from custom_widgets.model_select import ModelEntry, PopupMenu
from custom_widgets.vimkey import VimKeyHandler
from models.main import get_completion


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

pallet= [
]
    

class VimHeader(urwid.WidgetWrap):
    def __init__(self, model_name=None, provider=None, mode=None, key_sequence=None):
        self.model_name = model_name or ""
        self.provider = provider or ""
        self.mode = mode or "Normal"
        self.key_sequence = key_sequence or ""
        self._update_header()

    def _mode_attr_name(self):
        return f'mode_{self.mode.lower()}'

    def _update_header(self):
        # Mode indicator with its own style
        mode_widget = urwid.Text(f" {self.mode.upper()} ")
        mode_attr = urwid.AttrMap(mode_widget, self._mode_attr_name())

        # Remaining info (normal header style)
        info_text = urwid.Text(f" {self.model_name} [{self.provider}]", align='left')

        # Left side: mode + info
        left_side = urwid.Columns([
            ('pack', mode_attr),
            ('weight', 1, info_text)
        ], dividechars=0)

        # Right side: key sequence
        right_side = urwid.Text(f"{self.key_sequence} ", align='right')

        # Whole header layout
        header_columns = urwid.Columns([
            ('weight', 1, left_side),
            ('pack', right_side)
        ])

        self._w = urwid.AttrMap(header_columns, 'header')

    def update(self, mode=None, model_name=None, provider=None, key_sequence=None):
        if mode is not None:
            self.mode = mode
        if model_name is not None:
            self.model_name = model_name
        if provider is not None:
            self.provider = provider
        if key_sequence is not None:
            self.key_sequence = key_sequence

        self._update_header()

class ChatApp:
    def __init__(self, chat_file, model, available_models):
        # Color palette: user, assistant messages, focus highlight, footer
        self._busy = False

        self.palette = [
            ('header', 'light gray', 'black'),
            ('mode_normal', 'black,bold', 'dark cyan'),
            ('mode_insert', 'black,bold', 'dark blue'),
            ('mode_visual', 'black,bold', 'dark magenta'),
            ('user', 'black', 'dark blue'),
            ('assistant', 'black', 'dark blue'),
            ('focus', 'black', 'white'),
            ('border', 'dark blue', 'default'),
            ('border_focus', 'white', 'default'),
            ('default', 'default', 'default'),
            ('selected', 'black', 'dark blue'),
        ]


        self.model = model
        print(model)
        self.available_models = available_models

        self.compelte = None
        threading.Thread(target=self.load_model, daemon=True).start()

        messages = []

        if chat_file is not None:
            self.chat_file = chat_file
            try:
                with open(self.chat_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        self.chat_history = ChatHistory(messages=messages)

        self.footer = VimHeader(model_name=model["name"], provider=model["provider"], mode="Normal", key_sequence="")

        self.main = VimKeyHandler(chat_history=self.chat_history, header=None, footer=self.footer)

        self.model_select = PopupMenu([ModelEntry(model) for model in self.available_models.values()], on_select=self.select_model, on_close=self.open_main_view)

        # Main loop with key handler
        self.loop = urwid.MainLoop(
            self.main,
            self.palette,
            unhandled_input=self.handle_input,
            input_filter=self.input_filter,
        )

    def load_model(self):
        # This method is used to load the model in a separate thread
        # to avoid blocking the main loop
        self.complete = get_completion(self.model)
        self.loop.draw_screen()

    def input_filter(self, input_list, raw_input):
        if 'window resize' in input_list:
            self.chat_history.rebuild()
        if self._busy:
            # filter out all “enter” presses
            return [k for k in input_list if k != 'enter']
        return input_list



    def selectable(self):
        return True

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
        self.complete = None
        threading.Thread(target=self.load_model, daemon=True).start()
        self.footer.update(model_name=self.model["name"], provider=self.model["provider"])
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

    def get_response(self):
        # add placeholder for assistant
        response_message = EditableChatBubble(content="", role='assistant') 
        self.chat_history.message_list.append(response_message)

        last_index = len(self.chat_history.message_list) - 1
        self.chat_history.set_focus(last_index, "below")

        self.loop.draw_screen()


        if self.complete is None:
            self.load_model()

        messages = [msg.to_dict() for msg in self.chat_history.message_list[:-1]]
        response = self.complete(model=self.model["name"], messages=messages) # type: ignore
        for chunk in response: # type: ignore
            response_message.content += chunk
            response_message.update()
            self.chat_history.set_focus_valign("bottom")
            self.loop.draw_screen()

    def write_changes(self):
        with open(self.chat_file, 'w', encoding='utf-8') as f:
            json.dump(self.chat_history.to_dict(), f, ensure_ascii=False, indent=2)

    def handle_input(self, key):
        if key == "enter":
            if self._busy:
                return None
            self._busy = True
            try:
                self.get_response()
            finally:
                self._busy = False
            return None


        elif key == 'ctrl e':
            idx = self.main.chat_history.focus_position
            self.edit_message_in_editor(idx)
            return None

        elif key == 'ctrl p':
            self.open_popup()
            return None

        elif key == 'q':
            # Tell Urwid to stop its MainLoop
            raise urwid.ExitMainLoop()

    def run(self):
        print("Starting chat application...")
        self.loop.run()

    def shutdown(self):
        self.write_changes()

