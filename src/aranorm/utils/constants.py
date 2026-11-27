"""Arabic character constants used by all processors.

All constants are module-level so they can be imported directly and used as
frozen sets or strings without re-creating them on every call.
"""

# ────────────────────────────────────────────────────────────────────────────
# Arabic letter inventory (Unicode Arabic block U+0600–U+06FF)
# ────────────────────────────────────────────────────────────────────────────

#: All Arabic letter code-points including hamza forms, alef variants, and
#: extended letters used in Farsi/Urdu loanwords.
ARABIC_LETTERS = frozenset(
    "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهويىٱ"
    # Extended Arabic letters (Farsi, Urdu influence, common in Gulf texts)
    "پچژگک"
)

#: Bare alef (no hamza, no madda).
ALEF = "ا"

#: Alef variants that should be normalised to bare ALEF.
ALEF_VARIANTS = frozenset("أإآٱ")

#: Hamza carrier forms that should be normalised to standalone hamza (ء).
HAMZA_CARRIERS = frozenset("ؤئ")

#: Standalone hamza.
HAMZA = "ء"

#: Taa marbuta.
TAA_MARBUTA = "ة"

#: Haa (target when normalising taa marbuta in dialectal contexts).
HAA = "ه"

#: Alef maqsura.
ALEF_MAQSURA = "ى"

#: Ya (target when normalising alef maqsura).
YA = "ي"

#: Tatweel / kashida character.
TATWEEL = "ـ"

# ────────────────────────────────────────────────────────────────────────────
# Diacritics (harakat + special marks)
# ────────────────────────────────────────────────────────────────────────────

#: Arabic vowel marks (fatha, damma, kasra, tanwin variants), shadda, sukun,
#: tatweel (also treated as a diacritic by the DiacriticsProcessor), and
#: supplementary combining marks from the Arabic Extended-A block.
DIACRITICS = frozenset(
    # Core harakat
    "\u064b"  # fathatan (ً)
    "\u064c"  # dammatan (ٌ)
    "\u064d"  # kasratan (ٍ)
    "\u064e"  # fatha (َ)
    "\u064f"  # damma (ُ)
    "\u0650"  # kasra (ِ)
    "\u0651"  # shadda (ّ)
    "\u0652"  # sukun (ْ)
    # Tatweel / kashida (also handled by TatweelProcessor)
    "\u0640"  # ـ
    # Extended Arabic combining marks
    "\u0670"  # superscript alef (ٰ)
    "\u0656"  # subscript alef (ٖ)
    "\u0655"  # hamza below (ٕ)
    "\u065c"  # vowel sign dot below (ٜ)
    "\u065f"  # wavy hamza below (ٟ)
    "\u0657"  # inverted damma (ٗ)
    "\u065a"  # vowel sign small v above (ٚ)
    "\u065b"  # vowel sign inverted small v above (ٛ)
    "\u065d"  # reversed damma (ٝ)
    "\u065e"  # fatha with two dots (ٞ)
    # Quranic annotation signs
    "\u06d6"  # small high ligature sad lam alef maksura
    "\u06d7"  # small high ligature qaf lam alef maksura
    "\u06d8"  # small high meem initial form
    "\u06d9"  # small high lam alef
    "\u06da"  # small high jeem
    "\u06db"  # small high three dots
    "\u06dc"  # small high seen
    "\u06df"  # small high rounded zero
    "\u06e0"  # small high upright rectangular zero
    "\u06e1"  # small high dotless head of khah
    "\u06e2"  # small high meem isolated form
    "\u06e3"  # small low seen
    "\u06e4"  # small high madda
    "\u06e7"  # small high meem
    "\u06e8"  # small high noon
    "\u06ea"  # empty centre low stop
    "\u06eb"  # empty centre high stop
    "\u06ec"  # rounded high stop
    "\u06ed"  # small low meem
)

# ────────────────────────────────────────────────────────────────────────────
# Digits
# ────────────────────────────────────────────────────────────────────────────

#: Arabic-Indic (Eastern Arabic) digit characters.
ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

#: Extended Arabic-Indic (Persian/Urdu) digit characters.
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

#: ASCII digit characters (normalisation target).
WESTERN_DIGITS = "0123456789"

# ────────────────────────────────────────────────────────────────────────────
# Punctuation normalisation map
# ────────────────────────────────────────────────────────────────────────────

#: Map from Arabic/Indic punctuation characters to their ASCII equivalents.
PUNCTUATION_REPLACEMENTS = {
    "،": ",",  # Arabic comma
    "؛": ";",  # Arabic semicolon
    "؟": "?",  # Arabic question mark
    "٪": "%",  # Arabic percent sign
    "٫": ".",  # Arabic decimal separator
    "٬": ",",  # Arabic thousands separator
    "«": '"',  # left double angle quotation
    "»": '"',  # right double angle quotation
    "\u200c": "",  # zero-width non-joiner
    "\u200d": "",  # zero-width joiner
    "\u200b": "",  # zero-width space
    "\u00a0": " ",  # non-breaking space → regular space
    "\u202f": " ",  # narrow no-break space → regular space
    "\ufeff": "",  # BOM / zero-width no-break space
}

# ────────────────────────────────────────────────────────────────────────────
# Presentation form ligatures (Unicode Arabic Presentation Forms-B)
# ────────────────────────────────────────────────────────────────────────────

#: Map from Arabic ligature presentation forms to their canonical equivalents.
LIGATURE_REPLACEMENTS = {
    "\ufefb": "لا",  # LAM ALEF
    "\ufef7": "لأ",  # LAM ALEF WITH HAMZA ABOVE
    "\ufef9": "لإ",  # LAM ALEF WITH HAMZA BELOW
    "\ufef5": "لآ",  # LAM ALEF WITH MADDA ABOVE
    # Isolated / final / initial / medial forms (presentation forms A & B)
    "\ufe80": "ء",  # ARABIC LETTER HAMZA ISOLATED FORM
    "\ufe81": "آ",  # ARABIC LETTER ALEF WITH MADDA ABOVE ISOLATED
    "\ufe82": "آ",  # ARABIC LETTER ALEF WITH MADDA ABOVE FINAL
    "\ufe83": "أ",  # ARABIC LETTER ALEF WITH HAMZA ABOVE ISOLATED
    "\ufe84": "أ",  # ARABIC LETTER ALEF WITH HAMZA ABOVE FINAL
    "\ufe85": "ؤ",  # ARABIC LETTER WAW WITH HAMZA ABOVE ISOLATED
    "\ufe86": "ؤ",  # ARABIC LETTER WAW WITH HAMZA ABOVE FINAL
    "\ufe87": "إ",  # ARABIC LETTER ALEF WITH HAMZA BELOW ISOLATED
    "\ufe88": "إ",  # ARABIC LETTER ALEF WITH HAMZA BELOW FINAL
    "\ufe89": "ئ",  # ARABIC LETTER YEH WITH HAMZA ABOVE ISOLATED
    "\ufe8a": "ئ",  # ARABIC LETTER YEH WITH HAMZA ABOVE FINAL
    "\ufe8b": "ئ",  # ARABIC LETTER YEH WITH HAMZA ABOVE INITIAL
    "\ufe8c": "ئ",  # ARABIC LETTER YEH WITH HAMZA ABOVE MEDIAL
    "\ufe8d": "ا",  # ARABIC LETTER ALEF ISOLATED
    "\ufe8e": "ا",  # ARABIC LETTER ALEF FINAL
    "\ufb50": "ٱ",  # ARABIC LETTER ALEF WASLA ISOLATED
}

# ────────────────────────────────────────────────────────────────────────────
# Repeated-character reduction
# ────────────────────────────────────────────────────────────────────────────

#: Default maximum allowed run length for repeated non-whitespace characters.
DEFAULT_REPEATED_CHAR_LIMIT = 2

# ────────────────────────────────────────────────────────────────────────────
# Dialect labels
# ────────────────────────────────────────────────────────────────────────────

#: All dialect labels recognised by the built-in heuristic identifier.
KNOWN_DIALECT_LABELS = frozenset(["EGY", "GLF", "LEV", "IRQ", "NOR", "TUN", "YEM", "SDN", "MTN", "MSA", "UNK"])
