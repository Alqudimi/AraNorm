# ROUND16 CLI — حالة نهائية (قبل ضغط السياق)

## اكتشافات مهمة عن CLI args (src/aranorm/cli.py)
- `normalize` ليس له `--text` flag — النص positional فقط: `main(["normalize", "نص"])`.
- `normalize` flags: --file, --output, --json, --preset, --keep-diacritics, --dialect-target, --batch-size, --workers (بدون --retry, --max-retries, --emit-steps-trace!).
- `stopwords` يتطلب نصًا positional: `main(["stopwords", "نص", "--mode", "remove"])` + --json, --scope.
- `batch`: يتطلب --file (required) + --format (csv/json/jsonl, default jsonl) + --output + --preset + --workers + --batch-size + --stream + --progress + --retry + --max-retries + --skip-errors (غير مؤكد كلها).
- batch report JSONL: المفتاح `normalized_text` وليس `normalized`.
- batch مع --output يطبع "Wrote N results to ..." إلى stdout.
- main(['normalize','نص','--output','/tmp/nope/x.txt']) → RC=1 (OSError branch يعمل).

## فجوات cli.py المتبقية (من coverage report منفصل، إجمالي 93% في run الكامل)
- missing: 92 (stdin normalize), 98 (stdin), 117-121 (output OSError), 134 (stop_words_removed), 153 (out.close), 156-160 (retry failed), 199-232 (stopwords), 269-271 (dialect plain), 288-290 (keywords stdin), 349-357 (summarize stdin), 389/394 (sentiment stdin), 469->473 (plugins failures), 596-598 (batch stream file not found), 610-613/618-622 (progress/skip_errors), 680 (csv), 692/694-698 (batch stdout + failed retry), 786-787 (spec no subcmd), 822-852 (stream status + cancelled), 1270-1271 (no handler), 1283 (__main__).
- ملاحظة: بعض الفجوات "غير قابلة" (1283 __main__ لا يُغطّى عبر main مباشرة — تغطى عبر test_main_module_entry_point الحالي).
- suite الحالي: tests/test_coverage_round16_cli.py — 46 اختبارًا، كلها تمر.

## الحالة العامة (آخر قياس كامل: 1464 passed, 6 skipped)
- إجمالي branch coverage: 99%.
- cli.py: 93% (21 branch partially missing)، pipeline: 98%، normalizer: 95%، language_detector: 94%، spec 100%، integrations/models 98-100%، similarity_matrix + text_diff_report 100%.

## المتبقي لـ Phase 6
1. إغلاق فجوات cli.py القابلة (stdin للكثير من الأوامر، batch csv/json/format، stream errors، spec no subcommand، serve بدون module) — الاختبارات الجديدة أُضيفت للتو، بعضها فشل بسبب args خاطئة — أُصلح: استخدم positional text بلا --text.
2. make verify نهائي.
3. تحديث ROUND16_STATE.md + تقرير الإصدار ROUND16_REPORT.md + أرشيف.
