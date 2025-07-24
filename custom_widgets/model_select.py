import urwid


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
