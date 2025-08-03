from setuptools import setup

setup(
    name='terminal_gpt',
    version='0.1',
    py_modules=['main', 'chat'],
    install_requires=[
        'litellm',
        'urwid',
    ],
    entry_points={
        'console_scripts': [
            'terminal_gpt = main:main',  # Assumes main() is your entry function
            'render_chat = render_chat:main',
        ],
    },
)

