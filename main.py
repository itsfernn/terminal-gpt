import argparse
import os
import subprocess
import tempfile

import tomllib

from chat import ChatApp


def load_config():
    config_path = os.path.expanduser("~/.config/terminal_gpt/config.toml")
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "rb") as f:
        return tomllib.load(f)

def set_api_keys(config):
    for key, value in config["providers"].items():
        api_key = value.get("api_key", None)
        api_key_cmd = value.get("api_key_cmd", None)
        if not api_key and api_key_cmd:
            try:
                api_key = subprocess.check_output(api_key_cmd, shell=True).decode().strip()
            except subprocess.CalledProcessError:
                pass
        if api_key:
            os.environ[f"{key.upper()}_API_KEY"] = api_key


def get_avaliable_models(config):
    available_models = []
    for key, value in config["providers"].items():
        if os.environ.get(f"{key.upper()}_API_KEY"):
            available_models.extend(value.get("models", []))
    return available_models


def main():
    ## argument parsing
    parser = argparse.ArgumentParser(description="Chat application with message history.")
    parser.add_argument('--chat-file', type=str, default=None,
                        help='Path to the chat history file (default: temp directory)')
    parser.add_argument('--model', type=str, default='gpt-4.1-mini', 
                        help='Model to use for chat (default: gpt-4.1-mini)')

    args = parser.parse_args()

    config = load_config()
    set_api_keys(config)
    models = get_avaliable_models(config)

    model = args.model if args.model else config.get("default_model", "gpt-4.1-mini")

    if not models:
        print("No models found in configuration. Please check your config.toml.")
        return

    if args.model not in models:
        print(f"Model '{args.model}' not found in configuration. Available models: {models}")
        return

    # Check if the chat file exists, if not, create a temporary one
    if args.chat_file is None:
        try:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
            chat_file = tf.name
        except Exception:
            print("Failed to create a temporary chat file. Please specify a valid chat file path.")
            return
    else:
        chat_file = args.chat_file

    ChatApp(chat_file, model, models).run()

if __name__ == "__main__":
    main()
