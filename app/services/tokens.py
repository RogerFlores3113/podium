import tiktoken


# Cache the encoder — it's expensive to initialize
_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in a string using the cl100k_base encoding.

    This encoding is used by GPT-4, GPT-4o, and text-embedding-3-*.
    Close enough for token budgeting even if the exact model differs slightly.
    """
    return len(_encoder.encode(text))