"""Example 09: Writing a custom processor and registering it.

Demonstrates the Processor contract, the ProcessorRegistry, and the
factory pattern — the extension points of AraNorm.
"""

from typing import Optional

from aranorm.core import ProcessorFactory, ProcessorRegistry
from aranorm.core.base import Processor, ProcessorContext


# ── 1. Define a processor by implementing the two-method contract ─────────────
class LeetToArabicProcessor(Processor):
    """Convert common leet-speak tokens to Arabic words."""

    name = "leet_to_arabic"

    LEET_MAP = {
        "3": "ع",
        "7": "ح",
        "5": "خ",
        "2": "ق",
    }

    def process(self, text: str, context: Optional[ProcessorContext] = None) -> str:
        result = text
        for leet, arabic in self.LEET_MAP.items():
            result = result.replace(leet, arabic)
        if context is not None:
            context.record(self.name)
        return result


# ── 2. Register it in a registry ──────────────────────────────────────────────
registry = ProcessorRegistry()
registry.register("leet_to_arabic", LeetToArabicProcessor)

print("Registered processors (sample):")
for name in registry.names():
    if "leet" in name or "alef" in name:
        print(f"  {name}")
print()

# ── 3. Create instances through the factory ───────────────────────────────────
factory = ProcessorFactory(registry)
processor = factory.create("leet_to_arabic")

output = processor.process("3rabi 7ubb 5alas")
print(f"Leet → Arabic: {output!r}")
print()

# ── 4. Track applied steps via the context ────────────────────────────────────
context = ProcessorContext()
result = processor.process("3rabi 7ubb", context)
print(f"applied_steps: {context.applied_steps}")
print()

# ── 5. Registry introspection ─────────────────────────────────────────────────
print(f"Registry size:      {len(registry)}")
print(f"Contains 'leet...': {'leet_to_arabic' in registry}")
print(f"Available names:    {len(factory.available())}")
print()

# Unknown names raise a helpful error
try:
    registry.get("nonexistent_processor")
except Exception as error:
    print(f"Unknown processor error: {type(error).__name__}")
