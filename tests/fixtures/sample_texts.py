"""Reusable text fixtures for AraNorm tests."""

from typing import Dict, List, Tuple

# ────────────────────────────────────────────────────────────────────────────
# Orthographic normalization fixtures
# ────────────────────────────────────────────────────────────────────────────

ALEF_VARIANTS: List[Tuple[str, str]] = [
    ("أحمد", "احمد"),
    ("إبراهيم", "ابراهيم"),
    ("آمن", "امن"),
    ("ٱلله", "الله"),
    ("أأ إإ آآ ٱٱ", "اا اا اا اا"),
]

HAMZA_VARIANTS: List[Tuple[str, str]] = [
    ("سؤال", "سءال"),
    ("شيئ", "شيء"),
    ("يسأل", "يسال"),  # alef with hamza above — normalized by ALEFProcessor
]

DIACRITICS_CASES: List[Tuple[str, str]] = [
    ("مَرْحَبًا", "مرحبا"),
    ("كِتَابٌ", "كتاب"),
    ("السَّلَامُ عَلَيْكُمْ", "السلام عليكم"),
    ("قُرْآنٌ كَرِيمٌ", "قرآن كريم"),  # آ is precomposed — not a diacritic
]

TATWEEL_CASES: List[Tuple[str, str]] = [
    ("مـرحـبـا", "مرحبا"),
    ("جمـيـل", "جميل"),
    ("يـاللـه", "يالله"),
]

DIGIT_CASES: List[Tuple[str, str]] = [
    ("١٢٣", "123"),
    ("٠٩٨", "098"),
    ("۱۲۳", "123"),
    ("١٠٠٠", "1000"),
]

LIGATURE_CASES: List[Tuple[str, str]] = [
    ("ﻻ", "لا"),
    ("ﻷ", "لأ"),
    ("ﻹ", "لإ"),
    ("ﻵ", "لآ"),
]

TAA_MARBUTA_CASES: List[Tuple[str, str]] = [
    ("مدرسة", "مدرسه"),
    ("جامعة", "جامعه"),
    ("كرة", "كره"),
]

ALEF_MAQSURA_CASES: List[Tuple[str, str]] = [
    ("على", "علي"),
    ("يُصلَّى", "يصلي"),
    ("مصطفى", "مصطفي"),
]

REPEATED_CHARS_CASES: List[Tuple[str, str]] = [
    ("يااااا", "ياا"),
    ("هههههه", "هه"),
    ("لا لاا لاا", "لا لاا لاا"),  # only 2 a's — no reduction
]

# ────────────────────────────────────────────────────────────────────────────
# Content cleaning fixtures
# ────────────────────────────────────────────────────────────────────────────

URL_CASES: List[Tuple[str, str]] = [
    ("زوروا https://example.com للمزيد", "زوروا  للمزيد"),
    ("http://foo.org/path?q=1&a=2 مقال جيد", " مقال جيد"),
    ("www.google.com أداة بحث", " أداة بحث"),
]

EMAIL_CASES: List[Tuple[str, str]] = [
    ("تواصل معنا على info@example.com", "تواصل معنا على "),
    ("user.name+tag@host.co.uk بريد", " بريد"),
]

MENTION_CASES: List[Tuple[str, str]] = [
    ("رد على @user1 ب @user2", "رد على   ب "),
    ("ذكر @ArabicNLP في المنشور", "ذكر  في المنشور"),
]

HASHTAG_CASES: List[Tuple[str, str]] = [
    ("#موضوع مهم", "موضوع مهم"),
    ("#ArabicNLP مكتبة رائعة", "ArabicNLP مكتبة رائعة"),
]

HTML_CASES: List[Tuple[str, str]] = [
    ("<b>نص عريض</b>", " نص عريض "),
    ("<p class='arabic'>محتوى</p>", " محتوى "),
    ("<!-- تعليق --> نص", "  نص"),
]

EMOJI_CASES: List[Tuple[str, str]] = [
    ("مرحبا 😊 العالم", "مرحبا  العالم"),
    ("❤️ أحبك كثيراً 🌹", " أحبك كثيراً "),
]

# ────────────────────────────────────────────────────────────────────────────
# Dialect identification fixtures
# ────────────────────────────────────────────────────────────────────────────

DIALECT_MARKERS: Dict[str, List[str]] = {
    "EGY": [
        "عايز حاجة دلوقتي",
        "ازاي حالك ياريس",
        "مش عارف ليه مش بتيجي",
    ],
    "GLF": [
        "شلونك وايد زين",
        "ابغى أشتري شي الحين",
        "شخبارك هذا اليوم",
    ],
    "LEV": [
        "شو بدك تعمل هلق",
        "كيفك كتير متزعل",
        "بدي أروح هلأ",
    ],
    "TUN": [
        "برشا ناس جاو للحفلة",
        "علاش ما جيتش",
        "ياسر شنوة",
    ],
    "NOR": [
        "بزاف ديال الناس واش مجاو",
        "باغي نمشي دابا",
    ],
}

# ────────────────────────────────────────────────────────────────────────────
# Arabizi fixtures
# ────────────────────────────────────────────────────────────────────────────

ARABIZI_SAMPLES: List[str] = [
    "7abibi shloanak el yom",
    "insha2allah bkra nshoof",
    "wallah 3ajib jidan",
    "yalla 3ala ra7tek",
    "tamam ma3ak 7a2",
    "sho akhbarak ya 3ammo",
    "ana mabsoot kteer",
]

# ────────────────────────────────────────────────────────────────────────────
# Full-pipeline end-to-end fixtures
# ────────────────────────────────────────────────────────────────────────────

PIPELINE_CASES: List[Dict] = [
    {
        "input": "شلونك حبيبي؟ https://t.co/abc 😊 وايد زين",
        "has_no_url": True,
        "has_no_emoji": False,  # emojis not stripped by default standard preset
        "dialect": "GLF",
    },
    {
        "input": "عايز أروح المطار دلوقتي ازاي",
        "has_no_url": True,
        "has_no_emoji": True,
        "dialect": "EGY",
    },
    {
        "input": "كيفك بدي أحكيك شو صار هلق",
        "has_no_url": True,
        "has_no_emoji": True,
        "dialect": "LEV",
    },
]

# ────────────────────────────────────────────────────────────────────────────
# Edge cases
# ────────────────────────────────────────────────────────────────────────────

EDGE_CASES: List[str] = [
    "",  # empty string
    " ",  # whitespace only
    "123",  # digits only
    "hello world",  # Latin only
    "مرحبا",  # single Arabic word
    "أ" * 1000,  # very long repeated character
    "مرحبا\nكيف\nحالك",  # multiline
    "\t مرحبا \t كيف \t حالك \t",  # tabs and spaces
    "،،،،،،",  # punctuation only
    "هههههههههههههههههه",  # laughter characters
]

# ────────────────────────────────────────────────────────────────────────────
# Batch processing fixtures
# ────────────────────────────────────────────────────────────────────────────

BATCH_100: List[str] = ["نص عربي للاختبار رقم {}".format(i) for i in range(50)] + [
    "Arabic test text number {}".format(i) for i in range(50)
]

BATCH_1000: List[str] = BATCH_100 * 10
