import urwid


class ModelEntry(urwid.WidgetWrap):
    def __init__(self, model):
        self.model = model
        self.name = model.get('name', 'Unknown Model')
        self.provider = model.get('provider', 'Unknown Provider')

        name_text = urwid.Text(self.name)
        provider_text = urwid.Text(self.provider, align='right')

        columns = urwid.Columns(
            [
                ('weight', 2, name_text),
                ('weight', 1, provider_text),
            ],
            dividechars=5
        )
        columns_attr = urwid.AttrMap(columns, attr_map="default", focus_map="focus")
        super().__init__(columns_attr)

    def selectable(self):
        return True

    def get_entry(self):
        return self.model

    def get_label(self):
        return self.name

class PopupMenu(urwid.WidgetWrap):
    def __init__(self, entries, on_select, on_close):
        self.on_select = on_select
        self.on_close = on_close

        self.menu = urwid.Pile(entries)
        ## add padding
        menu_padding = urwid.Padding(self.menu, left=2, right=2)
        frame = urwid.LineBox(menu_padding, title="Select a Model")

        super().__init__(frame)

    def keypress(self, size, key):
        # j/k → down/up in the ListBox
        if key == 'j':
            return self.menu.keypress(size, 'down')  # type: ignore
        elif key == 'k':
            return self.menu.keypress(size, 'up')   # type: ignore
        elif key == 'enter':
            # Enter → select the focused model
            print("enter pressed")
            if self.menu.focus is not None:
                print("menu.focus is not None")
                selection = self.menu.focus.get_entry()
                print(f"selection: {selection}")
                self.on_select(selection)
            else:
                print("menu.focus is None")
                self.on_close()
            return None
        elif key in ('q', 'esc'):
            # q/esc → close the popup
            self.on_close()
            return None
        # let Enter and others flow through: buttons handle Enter themselves
        return super().keypress(size, key)
