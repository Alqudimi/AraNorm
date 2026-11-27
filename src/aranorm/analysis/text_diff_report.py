"""Token-level diff reporting between two Arabic texts.

The :class:`TextDiffReport` describes the sequence of edits that transforms
one text into another at the token level.  It is useful for explaining what
a normalization pipeline actually changed, or for highlighting divergence
between parallel corpora.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from aranorm.core.pipeline import NormalizationResult


@dataclass(frozen=True)
class DiffToken:
    """A single token operation in a :class:`TextDiffReport`.

    Attributes
    ----------
    op:
        One of ``"equal"``, ``"insert"``, ``"delete"``, ``"replace"``.
    before:
        Tokens from the source text (empty for pure insertions).
    after:
        Tokens from the target text (empty for pure deletions).
    """

    op: str
    before: List[str]
    after: List[str]

    def to_dict(self) -> Dict[str, object]:
        """Return a plain dictionary representation."""
        return {
            "op": self.op,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class TextDiffResult:
    """The complete token-level diff between two texts.

    Attributes
    ----------
    source:
        The original source text.
    target:
        The target (normalized) text.
    tokens_source:
        Whitespace-tokenized source tokens.
    tokens_target:
        Whitespace-tokenized target tokens.
    diff:
        Ordered list of :class:`DiffToken` operations.
    similarity_ratio:
        ``SequenceMatcher`` ratio between the token sequences (0-1).
    inserted_count:
        Number of tokens that appear only in the target.
    deleted_count:
        Number of tokens that appear only in the source.
    changed_count:
        Number of tokens that were replaced.
    unchanged_count:
        Number of tokens that are identical in both texts.
    """

    source: str
    target: str
    tokens_source: List[str]
    tokens_target: List[str]
    diff: List[DiffToken]
    similarity_ratio: float
    inserted_count: int
    deleted_count: int
    changed_count: int
    unchanged_count: int

    @property
    def is_identical(self) -> bool:
        """Return *True* when the two texts tokenize to identical sequences."""
        return self.tokens_source == self.tokens_target

    def to_dict(self) -> Dict[str, object]:
        """Return a plain dictionary representation."""
        return {
            "source": self.source,
            "target": self.target,
            "tokens_source": self.tokens_source,
            "tokens_target": self.tokens_target,
            "diff": [operation.to_dict() for operation in self.diff],
            "similarity_ratio": self.similarity_ratio,
            "inserted_count": self.inserted_count,
            "deleted_count": self.deleted_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        """Return a JSON serialization of the diff result."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def _tokenize(text: str) -> List[str]:
    """Split *text* on whitespace, dropping empty fragments."""
    return [token for token in text.split() if token]


class TextDiffReport:
    """Describe the token-level differences between two Arabic texts.

    Example
    -------
    >>> report = TextDiffReport()
    >>> result = report.diff("أنا سعيد", "أنا فرحان")
    >>> result.is_identical
    False
    """

    def diff(self, source: str, target: str) -> TextDiffResult:
        """Compute the token-level diff from *source* to *target*.

        Parameters
        ----------
        source:
            Original text.
        target:
            Text to compare against (typically the normalized version).
        """
        tokens_source = _tokenize(source)
        tokens_target = _tokenize(target)
        matcher = difflib.SequenceMatcher(None, tokens_source, tokens_target)
        diff: List[DiffToken] = []
        inserted = deleted = changed = unchanged = 0
        for tag, i_start, i_end, j_start, j_end in matcher.get_opcodes():
            before = tokens_source[i_start:i_end]
            after = tokens_target[j_start:j_end]
            if tag == "equal":
                diff.append(DiffToken(op="equal", before=before, after=after))
                unchanged += len(before)
            elif tag == "insert":
                diff.append(DiffToken(op="insert", before=[], after=after))
                inserted += len(after)
            elif tag == "delete":
                diff.append(DiffToken(op="delete", before=before, after=[]))
                deleted += len(before)
            else:
                diff.append(DiffToken(op="replace", before=before, after=after))
                changed += max(len(before), len(after))
        return TextDiffResult(
            source=source,
            target=target,
            tokens_source=tokens_source,
            tokens_target=tokens_target,
            diff=diff,
            similarity_ratio=matcher.ratio(),
            inserted_count=inserted,
            deleted_count=deleted,
            changed_count=changed,
            unchanged_count=unchanged,
        )

    @classmethod
    def from_normalization(
        cls,
        source: str,
        result: NormalizationResult,
    ) -> TextDiffResult:
        """Build a diff report from a normalization pipeline result.

        Parameters
        ----------
        source:
            The original input text.
        result:
            :class:`NormalizationResult` produced by a pipeline stage.
        """
        instance = cls()
        return instance.diff(source, result.normalized_text)
