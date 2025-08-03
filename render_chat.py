#!/usr/bin/env python3
import json
import shutil
import sys

from wcwidth import wcswidth

palette = [
    ('user', 'black', 'dark blue'),
    ('assistant', 'black', 'dark green'),
    ('user-border', 'dark blue', 'default'),
    ('assistant-border', 'dark green', 'default')
]

# Simple color mapping (can expand this for full ANSI)
ANSI_COLORS = {
    'black': 30, 'dark red': 31, 'dark green': 32, 'brown': 33,
    'dark blue': 34, 'dark magenta': 35, 'dark cyan': 36, 'light gray': 37,
    'dark gray': 90, 'light red': 91, 'light green': 92, 'yellow': 93,
    'light blue': 94, 'light magenta': 95, 'light cyan': 96, 'white': 97,
}

def get_ansi_code(attr_name):
    for name, fg, bg in palette:
        if name == attr_name:
            fg_code = ANSI_COLORS.get(fg, None)
            if fg_code is not None:
                bg_code = ANSI_COLORS.get(bg, None)
                if bg_code is not None:
                    bg_code += 10  # Background colors are fg + 10
                    return f"\033[{fg_code};{bg_code}m"
                else:
                    return f"\033[{fg_code}m"
    return "\033[0m"  # reset


def add_styling(lines, attr):
    """Add styling to each line based on the attribute."""
    styled_lines = []
    ansi_code = get_ansi_code(attr)
    for line in lines:
        styled_lines.append(f"{ansi_code}{line}\033[0m")  # reset after each line
    return styled_lines

def add_border(lines):
    """Add a margin to each line."""
    ' ' 
    length = wcswidth(lines[0]) +2
    lines = [' '  + line  + ' ' for line in lines]
    top = '▄'*length
    bot = '▀'*length
    return top, lines, bot

def add_alignment(lines: list[str], offset, align):
    """Align lines to the left, right, or center based on the specified alignment."""
    aligned_lines = []
    if align == 'left':
        return lines
    for line in lines:
        width = len(line)-2+offset
        if align == 'right':
            aligned_lines.append(line.rjust(width))
        elif align == 'center':
            aligned_lines.append(line.center(width))
        else:
            raise ValueError(f"Unknown alignment: {align}")
    return aligned_lines


def add_padding(lines, max_width):
    """Add padding to each line to ensure they are of equal length."""
    padded_lines = []
    for line in lines:
        if len(line) < max_width:
            padded_line = line.ljust(max_width)
        else:
            padded_line = line[:max_width]  # truncate if too long
        padded_lines.append(padded_line)
    return padded_lines




def word_wrap(lines,  max_width):
    longest_line_length = max(len(line) for line in lines)

    if longest_line_length < max_width:
        return lines

    result_lines = []
    for line in lines:
        words = line.split()
        if not words:
            # empty line
            result_lines.append('')
            continue

        current_line = words[0]
        for word in words[1:]:
            if len(current_line) + 1 + len(word) <= max_width:
                current_line += ' ' + word
            else:
                result_lines.append(current_line)
                current_line = word

        # add the last line from current_line
        result_lines.append(current_line)

    return result_lines

def get_width(lines, max_width):
    longest_line_width = max(len(line) for line in lines)
    return min(longest_line_width, max_width)


def render_chat_file(chat_file: str, cols: int) -> None:
    """Render chat messages from a JSON file to the terminal."""
    try:
        with open(chat_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {chat_file}", file=sys.stderr)
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from file: {chat_file}", file=sys.stderr)
        return

    string = ''

    for message in messages:
        content = message.get('content', '')
        role = message.get('role', 'user')

        lines = content.split('\n')
        block_size = get_width(lines, max_width=int(cols * 0.7))
        lines = word_wrap(lines, max_width=block_size)
        lines = add_padding(lines, max_width=block_size)
        top, lines, bot = add_border(lines)
        lines = add_styling(lines, role)
        top, bot = add_styling((top, bot), f"{role}-border")

        lines = [top]+lines+[bot]

        lines = add_alignment(lines, cols-block_size, {'user': 'right', 'assistant': 'left'}.get(message.get('role', 'user'), 'center'))

        string += '\n'.join(lines) + '\n'

    print(string)


def main():
    if len(sys.argv) < 2:
        print("Usage: render_chat FILE.json", file=sys.stderr)
        sys.exit(1)
    size = shutil.get_terminal_size()
# else get terminal size

    chat_file = sys.argv[1]
    # else get terminal size
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else size.columns

    render_chat_file(chat_file, cols)


if __name__ == "__main__":
    main()

