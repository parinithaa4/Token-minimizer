"""Vendored copy of JTF — JSON Token Format.

This is a verbatim vendoring of the ``jtf`` reference Python implementation
(https://github.com/k1y0miiii/jtf) so the gateway has zero external runtime
dependencies for its differentiating feature. It is MIT licensed.

    Copyright (c) 2026 Maxim Chumakov
    SPDX-License-Identifier: MIT

See ``_vendor/jtf/LICENSE`` for the full license text.

JTF is a lossless, round-trippable encoding of the JSON data model that
reduces LLM tokenizer token count when passing structured data to models::

    from llm_gateway._vendor.jtf import encode, decode

    text = encode(data)   # JSON-compatible Python object -> JTF string
    obj  = decode(text)   # JTF string -> Python object

Round-trip guarantee: ``decode(encode(x)) == x`` for any JSON-serializable
Python value.
"""

from .core import encode, decode
from .cost import heuristic_cost, tiktoken_cost

__all__ = ["encode", "decode", "heuristic_cost", "tiktoken_cost", "__version__"]

__version__ = "1.0.0"
