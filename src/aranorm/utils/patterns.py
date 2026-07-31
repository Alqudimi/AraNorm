"""Compiled regular expression patterns."""

import re

# URLs: http/https/www
URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)\S+")

# Email addresses
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Social media @mentions — supports Latin and Arabic usernames
MENTION_PATTERN = re.compile(r"(?<!\w)@[\w\u0600-\u06FF]+")

# Hashtags — keeps the text, strips the # marker
HASHTAG_PATTERN = re.compile(r"(?<!\w)#([^\s#]+)")

# HTML tags
HTML_PATTERN = re.compile(r"<[^>]+>")

# Repeated punctuation runs (e.g., ؟؟؟ !!! ,,,)
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([!?.,،؛:؟])\1+")

# Spaces around punctuation
SPACES_AROUND_PUNCTUATION_PATTERN = re.compile(r"\s*([!?.,،؛:؟])\s*")

# Multiple whitespace characters
MULTI_SPACE_PATTERN = re.compile(r"\s+")

# Arabizi tokens: Latin letters plus common digit substitutions
ARABIZI_WORD_PATTERN = re.compile(r"[A-Za-z0-9@3'7'8'9$]+")
