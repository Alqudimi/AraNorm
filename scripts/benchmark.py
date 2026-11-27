"""Benchmark AraNorm pipeline performance.

Usage:
    python scripts/benchmark.py                 # full benchmark
    python scripts/benchmark.py --quick         # quick smoke test (100 texts)
    python scripts/benchmark.py --preset deep   # specific preset only
    python scripts/benchmark.py --stream         # benchmark bounded process_iter

Example output:
    Preset 'light'    | 1000 texts | 0.42s | 2380 texts/s
    Preset 'standard' | 1000 texts | 0.61s | 1639 texts/s
    Preset 'deep'     | 1000 texts | 0.74s | 1351 texts/s
    Preset 'social_media' | 1000 texts | 0.70s | 1428 texts/s
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path
from typing import List, Optional

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aranorm import ArabicNormalizationPipeline, PipelineConfig  # noqa: E402

# ────────────────────────────────────────────────────────────────────────────
# Sample corpora
# ────────────────────────────────────────────────────────────────────────────

_DIALECT_SAMPLES: List[str] = [
    "شلونك حبيبي؟ وايد زين والله",
    "عايز أعرف ازاي أروح المطار دلوقتي",
    "كيفك شو أخبارك بدي أشوفك هلق",
    "برشا ناس جاو للمهرجان واش هو مليح",
    "أكو ناس هواية ما يعرفون شلون يحكون",
    "أنا مش فاهم ليه مش بتيجي",
    "الحين نروح ابغى أشتري شي وايد حلو",
    "شو بدك تعمل هلق هيك؟ منيح كتير",
    "بزاف الناس باغيين يتعلمو العربية",
    "إنشالله تكون بخير وصحة وسلامة",
]

_MSA_SAMPLES: List[str] = [
    "أعلن الرئيس عن خطة لتطوير القطاع الاقتصادي",
    "تشير الدراسات إلى تزايد الاهتمام بتعلم اللغة العربية",
    "وقّعت الدول الأعضاء على الاتفاقية الدولية للتجارة",
    "تمكّن الباحثون من اكتشاف دواء جديد يعالج المرض",
    "أكد المسؤولون ضرورة التعاون الإقليمي لمواجهة التحديات",
]

_SOCIAL_MEDIA_SAMPLES: List[str] = [
    "RT @user: يااارب يكون الجو حلو 😊❤️ #اليوم #الطقس https://t.co/example",
    "هههههه مت من الضحك 😂😂😂 شوفو ها الفيديو https://youtu.be/xyz #مضحك",
    "<b>عاجل</b>: إيهاب يلعب في @نادي_الأهلي #كرة_القدم 🏆",
    "صباح النور 🌞 شلونكم اليوم؟ إنشالله بخير وعافية 💚",
    "@أحمد تعال هنا لما تخلص https://example.com/path?q=test&lang=ar",
    "يلا نروح نتعشى 🍽️ مطعم <<الأصيل>> وايد زين! #مطعم #رياض",
    "مـرحـبـا بـكـم جميعـاً ~~~~ هههههههههه يااااا سلام عليكم",
    "تكذب؟؟؟ والله لا أقبل هذا الكلام! مشكلة كبيرة جداً جدا جدا!",
]

_ARABIZI_SAMPLES: List[str] = [
    "ana mabsoot kteer min el kalam da",
    "7abibi kifak shloanak el yom",
    "yalla 3ala ra7tek wenta meshi",
    "wallah 3ajib jidan this book",
    "sho akhbarak ya 3ammo",
    "insha2allah bkra nshoof",
    "tamam ma3ak 7a2 w ana ghala6",
]

# Combined corpus for full benchmark
_ALL_SAMPLES: List[str] = _DIALECT_SAMPLES + _MSA_SAMPLES + _SOCIAL_MEDIA_SAMPLES + _ARABIZI_SAMPLES


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _build_corpus(n: int, base: Optional[List[str]] = None) -> List[str]:
    """Return a corpus of exactly *n* texts by cycling over *base*."""
    source = base or _ALL_SAMPLES
    return [source[i % len(source)] for i in range(n)]


def _run_preset(
    preset: str,
    n: int,
    n_workers: int = 1,
    batch_size: int = 32,
    stream: bool = False,
) -> dict:
    """Benchmark a single preset and return timing statistics."""
    corpus = _build_corpus(n)
    if preset == "social_media":
        corpus = _build_corpus(n, _SOCIAL_MEDIA_SAMPLES)
    elif preset in ("light", "standard"):
        corpus = _build_corpus(n, _DIALECT_SAMPLES + _MSA_SAMPLES)

    config = PipelineConfig(preset=preset, handle_arabizi=(preset == "deep"))
    pipeline = ArabicNormalizationPipeline(config=config)

    # Warmup
    pipeline.process(corpus[0])

    times: List[float] = []
    runs = 3
    for _ in range(runs):
        t0 = time.perf_counter()
        if stream:
            for _ in pipeline.process_iter(corpus, batch_size=batch_size, n_workers=n_workers):
                pass
        else:
            pipeline.process_batch(corpus, batch_size=batch_size, n_workers=n_workers)
        times.append(time.perf_counter() - t0)

    best = min(times)
    mean = statistics.mean(times)
    throughput = n / best
    return {
        "preset": preset,
        "n_texts": n,
        "best_s": best,
        "mean_s": mean,
        "texts_per_second": throughput,
    }


def _print_header() -> None:
    print(f"\n{'Preset':<15} {'Texts':>7} {'Best(s)':>8} {'Mean(s)':>8} {'texts/s':>10}")
    print("-" * 53)


def _print_row(r: dict) -> None:
    print(
        f"{r['preset']:<15} {r['n_texts']:>7} "
        f"{r['best_s']:>8.3f} {r['mean_s']:>8.3f} {r['texts_per_second']:>10.0f}"
    )


# ────────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AraNorm pipeline benchmark")
    parser.add_argument("--quick", action="store_true", help="Use only 100 texts")
    parser.add_argument(
        "--preset",
        choices=["light", "standard", "deep", "social_media", "all"],
        default="all",
        help="Preset(s) to benchmark",
    )
    parser.add_argument("--n", type=int, default=1000, help="Number of texts (ignored if --quick)")
    parser.add_argument("--workers", type=int, default=1, help="Thread workers for batch")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size hint")
    parser.add_argument(
        "--stream", action="store_true", help="Benchmark bounded process_iter instead of materialized process_batch"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    n = 100 if args.quick else args.n
    presets = ["light", "standard", "deep", "social_media"] if args.preset == "all" else [args.preset]

    mode = "process_iter (streaming)" if args.stream else "process_batch"
    print(f"\nAraNorm Benchmark  (n={n}, workers={args.workers}, mode={mode})")
    _print_header()

    results = []
    for preset in presets:
        r = _run_preset(
            preset,
            n=n,
            n_workers=args.workers,
            batch_size=args.batch_size,
            stream=args.stream,
        )
        _print_row(r)
        results.append(r)

    # Throughput summary
    if len(results) > 1:
        best_preset = max(results, key=lambda x: x["texts_per_second"])
        print(f"\nFastest: '{best_preset['preset']}' at {best_preset['texts_per_second']:.0f} texts/s")

    # Performance gate check (non-fatal)
    light = next((r for r in results if r["preset"] == "light"), None)
    if light and light["texts_per_second"] < 500:
        print(f"\n⚠  'light' preset is below 500 texts/s on this system ({light['texts_per_second']:.0f} texts/s)")
    elif light:
        print(f"\n✓  'light' preset passes the ≥500 texts/s gate ({light['texts_per_second']:.0f} texts/s)")


if __name__ == "__main__":
    main()
