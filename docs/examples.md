# AraNorm — Examples

## 1. تنظيف بيانات تويتر (Twitter Data Cleaning)

تنظيف تغريدة كاملة تحتوي على روابط ومنشنات وهاشتاجات وإيموجي:

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.processors import TwitterNormalizer

# تنظيف تلقائي بـ preset مخصص للسوشيال ميديا
pipeline = ArabicNormalizationPipeline(
    PipelineConfig(
        preset="social_media",
        normalize_alef=True,
        normalize_hamza=True,
        remove_diacritics=True,
        normalize_tatweel=True,
        normalize_repeated_chars=True,
    )
)

tweet = "RT @أحمد: شلونك ياااا؟ 😊 https://t.co/abc #السعودية #ترند"
result = pipeline.process(tweet)
print(result.normalized_text)
# → "شلونك ياا؟ السعودية ترند"
print(result.dialect)
# → "GLF"
print(result.applied_steps)
# → ['remove_html_tags', 'remove_urls', 'remove_emails', 'remove_mentions',
#    'remove_emojis', 'normalize_whitespace', 'normalize_unicode', ...]

# أو استخدام TwitterNormalizer مباشرة
normalizer = TwitterNormalizer(
    remove_rt=True,
    expand_hashtags=True,
    remove_mentions=True,
)
cleaned = normalizer.process(tweet)
print(cleaned)
# → "شلونك ياااا؟ 😊 السعودية ترند"
```

---

## 2. تطبيع لهجة مصرية إلى الفصحى (Egyptian → MSA)

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig

pipeline = ArabicNormalizationPipeline(
    PipelineConfig(
        preset="deep",
        dialect_target="msa",
        normalize_alef=True,
        normalize_hamza=True,
        remove_diacritics=True,
        normalize_tatweel=True,
    )
)

texts = [
    "عايز أروح المطار دلوقتي ازاي",
    "مش فاهم ليه مش بتيجي",
    "يلا بينا الأكل جاهز بقى",
]

results = pipeline.process_batch(texts, batch_size=16)
for r in results:
    print(f"[{r.dialect:>3}] {r.original_text!r}")
    print(f"      → {r.msa_text!r}")
    print()

# [EGY] 'عايز أروح المطار دلوقتي ازاي'
#       → 'يريد أروح المطار الآن كيف'
# [EGY] 'مش فاهم ليه مش بتيجي'
#       → 'ليس فاهم لماذا ليس بتيجي'
```

---

## 3. تطبيع نصوص Arabizi (Arabic in Latin Script)

```python
from aranorm import ArabicNormalizationPipeline, PipelineConfig
from aranorm.processors import ArabiziProcessor

# معالجة منفردة
processor = ArabiziProcessor()
texts = [
    "7abibi shloanak el yom",
    "insha2allah bkra nshoof",
    "wallah 3ajib jidan",
    "yalla 3ala ra7tek",
]

for text in texts:
    print(f"{text!r:40s} → {processor.process(text)!r}")

# 'insha2allah bkra nshoof'   → 'إنشاءالله بكرا نشوف'

# عبر الـ Pipeline مع تفعيل handle_arabizi
pipeline = ArabicNormalizationPipeline(
    PipelineConfig(
        preset="standard",
        handle_arabizi=True,
        normalize_alef=True,
        remove_diacritics=True,
    )
)

result = pipeline.process("7abibi 3amel eh")
print(result.normalized_text)
```

---

## 4. بناء Pipeline مخصص (Custom Pipeline)

```python
from aranorm import ArabicNormalizationPipeline

# استخدام Builder Pattern
pipeline = (
    ArabicNormalizationPipeline.builder()
    .add_cleaner(
        remove_urls=True,
        remove_emojis=True,
        remove_html=True,
        remove_mentions=True,
    )
    .add_normalizer(
        normalize_alef=True,
        normalize_hamza=True,
        normalize_diacritics=True,
        normalize_tatweel=True,
        normalize_digits=True,
    )
    .add_dialect_processor(
        identify=True,
        normalize_to="coda",
        supported_dialects=["EGY", "GLF", "LEV", "NOR"],
    )
    .build()
)

texts = [
    "أهلاً <b>وسهلاً</b> 🎉 https://example.com",
    "هاذا الاشياء مش مزبوطة",
    "وايد ناس ما يعرفون",
]

results = pipeline.process_batch(texts, batch_size=32, n_workers=2)
for r in results:
    print(f"dialect={r.dialect:<5} normalized={r.normalized_text!r}")
    if r.coda_text:
        print(f"          coda    ={r.coda_text!r}")
```

---

## 5. استخدام Processor مفرد (Single Processor)

```python
from aranorm.processors import (
    ALEFProcessor,
    DiacriticsProcessor,
    HamzaProcessor,
    TatweelProcessor,
)

# كل Processor قابل للاستخدام المستقل
processors_demo = [
    (ALEFProcessor(),       "أحمد إبراهيم آمن ٱلله"),
    (HamzaProcessor(),      "سؤال شيئ مؤمن"),
    (DiacriticsProcessor(), "مَرْحَبًا بِكُمْ"),
    (TatweelProcessor(),    "مـرحـبـا بـكـم"),
]

for proc, text in processors_demo:
    print(f"{proc.name:<25s} | {text!r:30s} → {proc.process(text)!r}")
```

---

## 6. مثال WhatsApp و Chat

```python
from aranorm.processors import ChatNormalizer, WhatsAppNormalizer

# WhatsApp
wa = WhatsAppNormalizer(
    expand_abbreviations=True,
    remove_media_markers=True,
    remove_formatting=True,
)
messages = [
    "انشاءالله الشغل يخلص بكره 🙏",
    "*مهم*: اجتماع الساعة ٣",
    "[صوت] سماع الرسالة الصوتية",
]
for msg in messages:
    print(f"WA: {wa.process(msg)!r}")

# Chat عام
chat = ChatNormalizer(normalize_laughter=True, expand_abbreviations=True)
posts = [
    "هههههههههه مات من الضحك 😂😂",
    "ان شاء الله نشوفك بكره يا صاحبي",
    "لوووول هذا الكلام مضحك وايد",
]
for post in posts:
    print(f"Chat: {chat.process(post)!r}")
```

---

## 7. تحديد اللهجة (Dialect Identification)

```python
from aranorm.stages import DialectIdentifier

identifier = DialectIdentifier()

samples = {
    "EGY": "عايز أروح المطار دلوقتي ازاي",
    "GLF": "شلونك وايد زين الحين أبغى شيء",
    "LEV": "شو بدك تعمل هلق كتير متعب",
    "TUN": "برشا ناس علاش ما جاوش",
    "NOR": "بزاف الناس باغيين يتعلمو",
    "MSA": "أعلن الرئيس عن خطة لتطوير القطاع الاقتصادي",
}

for expected_dialect, text in samples.items():
    result = identifier.identify(text)
    status = "✓" if result.dialect_label == expected_dialect else "✗"
    print(
        f"{status} [{expected_dialect}→{result.dialect_label:>3}] "
        f"conf={result.confidence_score:.2f} | {text[:40]!r}"
    )
```

---

## 8. المعالجة الدفعية الموازية (Parallel Batch Processing)

```python
import time
from aranorm import ArabicNormalizationPipeline, PipelineConfig

# توليد 10,000 نص تجريبي
corpus = [
    "شلونك حبيبي؟ نص رقم {}".format(i) for i in range(10_000)
]

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="light"))

# معالجة متسلسلة
t0 = time.perf_counter()
pipeline.process_batch(corpus, batch_size=64, n_workers=1)
t1 = time.perf_counter()

# معالجة متوازية (4 خيوط)
t2 = time.perf_counter()
pipeline.process_batch(corpus, batch_size=64, n_workers=4)
t3 = time.perf_counter()

print(f"Sequential : {t1-t0:.2f}s  ({len(corpus)/(t1-t0):.0f} texts/s)")
print(f"4 workers  : {t3-t2:.2f}s  ({len(corpus)/(t3-t2):.0f} texts/s)")
```

---

## 9. التكامل مع نماذج اللغة (Optional ML Integration)

```python
# تثبيت: pip install "aranorm[ml]"
from aranorm.stages.dialect_norm import DialectNormalizer, ModelDialectStrategy

# استخدام نموذج AraT5 للـ CODA (يتطلب تحميل النموذج)
coda_strategy = ModelDialectStrategy(
    model_name="CAMeL-Lab/arabart",  # استبدل بالنموذج المناسب
    device="cuda:0",                  # أو "cpu"
    max_new_tokens=128,
)
normalizer = DialectNormalizer("coda", coda_strategy=coda_strategy)
result = normalizer.process("شلونك حبيبي وايد مبسوط")
print(result)
```

---

## 10. التسجيل والمتابعة (Logging)

```python
import logging
from aranorm import ArabicNormalizationPipeline, PipelineConfig

# تفعيل logs مفصلة
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)

pipeline = ArabicNormalizationPipeline(PipelineConfig(preset="standard"))
result = pipeline.process("أحمد إبراهيم")
print(f"Applied: {result.applied_steps}")
```
