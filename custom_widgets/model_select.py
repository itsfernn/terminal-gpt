import urwid


class MenuEntry(urwid.WidgetWrap):
    def __init__(self, label):
        self.label = label
        text = urwid.Text(label, align='center')
        attr_map = urwid.AttrMap(text, 'default', focus_map='selected')
        super().__init__(attr_map)

    def selectable(self):
        return True

    def get_label(self):
        return self.label

class PopupMenu(urwid.WidgetWrap):
    def __init__(self, models, on_select, on_close):
        self.on_select = on_select
        self.on_close = on_close

        # Build a ListBox of Buttons
        entries = [
            MenuEntry(model) for model in models
        ]

        self.menu = urwid.Pile(entries)
        # add margin around
        self.menu = urwid.Padding(self.menu, left=2, right=2)
        

        # Put it in a LineBox for a border/title
        frame = urwid.LineBox(self.menu, title="Select a Model")

        # Initialize the WidgetWrap with that outer frame
        super().__init__(frame)

    def keypress(self, size, key):
        # j/k → down/up in the ListBox
        if key == 'j':
            return self.menu.keypress(size, 'down')  # type: ignore
        elif key == 'k':
            return self.menu.keypress(size, 'up')   # type: ignore
        elif key == 'enter':
            # Enter → select the focused model
            if self.menu.focus is not None:
                assert isinstance(self.menu.focus, MenuEntry), "Focused item must be a MenuEntry"
                selected_model = self.menu.focus.get_label()
                self.on_select(selected_model)
            else:
                self.on_close()
            return None
        elif key in ('q', 'esc'):
            # q/esc → close the popup
            self.on_close()
            return None
        # let Enter and others flow through: buttons handle Enter themselves
        return super().keypress(size, key)
