---
name: Bug report
about: Report something that is not working as expected
title: "[Bug] "
labels: bug
assignees: ''
---

**وصف المشكلة | Describe the bug**
وصف واضح ومختصر للمشكلة.
A clear and concise description of what the bug is.

**خطوات إعادة الإنتاج | To reproduce**
Steps to reproduce the behavior:

```python
from aranorm import ArabicNormalizationPipeline
pipeline = ArabicNormalizationPipeline.from_preset("standard")
result = pipeline.process("...")
# ماذا حدث؟
```

**السلوك المتوقع | Expected behavior**
ما كنت تتوقع أن يحدث.
What you expected to happen.

**البيئة | Environment**
 - OS: [e.g. Ubuntu 24.04]
 - Python version: [e.g. 3.12]
 - AraNorm version: [e.g. 1.15.0] — `aranorm version`
 - Installed extras: [none / camel / ml / full]

**سياق إضافي | Additional context**
أي سياق آخر: نص الإدخال الكامل، رسالة الخطأ، traceback...
Any other context: full input text, error message, traceback...
