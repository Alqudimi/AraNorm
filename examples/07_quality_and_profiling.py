"""Example 07: Quality scoring, spelling reports, and one-pass profiling.

Demonstrates the quality/correctness analyzers and the unified 22-axis profiler.
"""

from aranorm.analysis import profile_text
from aranorm.analysis.quality_score import analyze_quality
from aranorm.analysis.spelling_report import analyze_spelling

TEXT = """
أعلنت الشركه عن نتائجها الماليه للربع الثالث من العام الحالي، حيث بلغت الأرباح
مليون ريال بزيادة قدرها عشره بالمئة. وقال الرئيس التنفيذي ان الشركة تسعى
لتوسيع نشاطاتها في المنطقه. وقال المسؤولون إن هذه الإصلاحات ستساهم في تعزيز
النمو الاقتصادي خلال السنوات القادمة، الا ان التحديات ما زالت قائمة.
"""

# ── 1. Composite quality score (8 weighted components) ────────────────────────
quality = analyze_quality(TEXT)
print(f"Quality Score: {quality.score:.1f}/100 ({quality.label})")
print("\nComponents:")
for component in quality.components:
    print(f"  {component.name:22} {component.score:5.1f}  (weight {component.weight:.2f})")
if quality.issues:
    print("\nIssues found:")
    for issue in quality.issues:
        print(f"  - {issue}")
if quality.suggestions:
    print("\nSuggestions:")
    for suggestion in quality.suggestions:
        print(f"  - {suggestion}")
print()

# ── 2. Spelling report with categorized corrections ───────────────────────────
spelling = analyze_spelling(TEXT)
print(f"Spelling: {spelling.spelling_issues_found} issues in "
      f"{spelling.total_words} words (correct ratio {spelling.correct_ratio:.0%})")
if spelling.corrections:
    print("\nCorrections:")
    for correction in spelling.corrections:
        print(f"  {correction.word:12} → {correction.replacement:12} "
              f"(x{correction.count}, {correction.category})")
print(f"\nCorrected text preview:\n  {spelling.corrected_text[:100]}...")
print()

# ── 3. One-pass 22-axis profiling ─────────────────────────────────────────────
profile = profile_text(TEXT)
print(f"Profiled axes: {len(profile.axes)}")
print("\nInsights:")
for insight in profile.insights:
    print(f"  [{insight.rule}] {insight.message}")
print()

# Inspect selected axes
for axis in ("quality", "readability", "sentiment"):
    if axis in profile.axes:
        summary = profile.axes[axis]
        # each axis value is a dict — show its top-level keys
        keys = list(summary.keys()) if isinstance(summary, dict) else ["value"]
        print(f"  axis '{axis}': {keys[:6]}")
