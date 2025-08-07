from typing import Iterator

from openai import OpenAI

# you can share one client across calls
client = OpenAI()

def complete(
    model: str,
    messages,
) -> Iterator[str]:
    """
    Stream-complete a chat-based model via the new OpenAI client.
    Yields each text delta as it arrives.

    Args:
        model: The name of the model (e.g. "gpt-4.1")
        messages: List of {"role": ..., "content": ...} dicts.
        client:   (optional) an existing OpenAI client instance.

    Yields:
        Each subsequent piece of generated text (str).
    """
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )

    for chunk in stream:
        # chunk.choices[0].delta might be {"content": "..."}
        delta = chunk.choices[0].delta
        if content := delta.content:
            yield content

        # if finish_reason is set, stop early
        if chunk.choices[0].finish_reason is not None:
            break

