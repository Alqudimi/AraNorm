"""Example 04: Using individual processors directly.

Demonstrates how to use AraNorm processors without the full pipeline.
"""

from aranorm.processors import (
    ALEFProcessor,
    ArabiziProcessor,
    ChatNormalizer,
    DiacriticsProcessor,
    EmojiProcessor,
    HamzaProcessor,
    RepeatedCharsProcessor,
    TatweelProcessor,
    TwitterNormalizer,
    URLProcessor,
    WhatsAppNormalizer,
)

# ── Orthographic processors ───────────────────────────────────────────────────
print("Orthographic Processors:")

alef = ALEFProcessor()
print(f"  ALEFProcessor:      {alef.process('أحمد إبراهيم آمن ٱلله')!r}")

hamza = HamzaProcessor()
print(f"  HamzaProcessor:     {hamza.process('سؤال شيئ مسألة')!r}")

diacritics = DiacriticsProcessor()
print(f"  DiacriticsProcessor:{diacritics.process('مَرْحَبًا بِكُمْ')!r}")

tatweel = TatweelProcessor()
print(f"  TatweelProcessor:   {tatweel.process('مـرحـبـا بـكـم')!r}")

repeated = RepeatedCharsProcessor()
print(f"  RepeatedChars:      {repeated.process('يياا سلام يااا')!r}")

print()

# ── Content cleaning processors ──────────────────────────────────────────────
print("Content Cleaning Processors:")

url_proc = URLProcessor()
print(f"  URLProcessor:   {url_proc.process('زر موقعنا https://example.com/path?q=1 للمزيد')!r}")

emoji_proc = EmojiProcessor()
print(f"  EmojiProcessor: {emoji_proc.process('مرحبا 😊 كيف حالك 🙏')!r}")

print()

# ── Platform processors ───────────────────────────────────────────────────────
print("Platform Processors:")

twitter = TwitterNormalizer()
print(f"  Twitter:  {twitter.process('RT @user: شلونك؟ #موضوع https://t.co/x')!r}")

whatsapp = WhatsAppNormalizer()
print(f"  WhatsApp: {whatsapp.process('انشالله الشغل يخلص بكره 🙏 *مهم*: اجتماع')!r}")

chat = ChatNormalizer()
print(f"  Chat:     {chat.process('هههههههههه مضحك جداً لمااا')!r}")

print()

# ── Arabizi processor ─────────────────────────────────────────────────────────
print("Arabizi Transliteration:")
arabizi = ArabiziProcessor()
samples = ["7abibi", "shu akhbarak", "3arabi"]
for s in samples:
    print(f"  {s!r:20} → {arabizi.process(s)!r}")
