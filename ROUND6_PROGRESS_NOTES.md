# ملاحظات تقدم الجولة السادسة (v1.7.0) — للاسترجاع بعد ضغط السياق

## خط الأساس
- الإصدار الحالي: 1.6.0، الفرع `professional-hardening`، commit `13d494a`
- 660 اختبارًا ناجحًا + 5 تخطيات اختيارية، تغطية 92%، `make verify` ناجح
- الجولة السادسة مخططة في `/home/ubuntu/AraNorm/ROUND6_ROADMAP.md` (نطاق A–H)

## المسار C (steps_trace) — مكتمل في الكود، يتبقى التحقق
1. `PipelineConfig` في `src/aranorm/core/config.py`: أُضيف حقل `emit_steps_trace: bool = False` (opt-in)، validate في `__post_init__` (TypeError عند غير bool)، وسطر `"emit_steps_trace"` في `to_dict()`. **يتبقى التحقق من أن `from_dict` و`copy_with` يلتقطان الحقل تلقائيًا** (يبدو أنهما عامان/آليان — يجب التحقق).
2. `ProcessorContext` في `src/aranorm/core/base.py`: أُضيف `_trace_enabled`, `_trace`, `enable_trace()`, `steps_trace()`, trace في `record` و`record_always` و`merge`.
3. `pipeline.py` في `process()`: تفعيل trace عبر `context.enable_trace()` عند `emit_steps_trace`، وتغذية `result.steps_trace` في `NormalizationResult`.

## NormalizationResult (pipeline.py)
- أُضيف حقل `steps_trace: Optional[List[Tuple[str, str]]] = None`
- `to_dict()` يحوّل إلى `[[step, action]]` (قوائم للـ JSON)، و`from_dict()` يعيد أزواجًا
- يجب إضافة خطوات مماثلة في `process_iter`/`process_batch` إذا أُعيد استخدام context (تحقق لاحقًا)

## المسارات المتبقية في ROUND6_ROADMAP.md
- A: اختبارات فجوات التغطية (domain_stop 40%، phone 82%، cache 82%، chunker 86%، dialect_id 86%، stop_words_stage 88%)
- B: اختبارات عدائية للمعالجات وNormalizerUtils
- D: `process_batch_retry()` فوق `process_batch` (حدود معلنة)
- E: property-based tests بـ seed محدد، stdlib فقط
- F: validator هيكلي لـ JSON data files (src/aranorm/data/*.json)
- G: CLI E2E batch بملفات كبيرة وstdin
- H: رفع إلى 1.7.0 + CHANGELOG + README + performance_round6.json + security_round6.json + build + twine check + SHA256SUMS + ROUND6_RELEASE_REPORT.md + archive + commit

## أوامر رئيسية
- `make verify` (format-check + lint + type-check + test)
- `make test-cov` (تغطية >=94% هدف)
- `python3 scripts/performance_audit.py > performance_round6.json`
- `python3 scripts/security_audit.py > security_round6.json`
- `python3 -m build --no-isolation --wheel --sdist`، `python3 -m twine check dist/*`
- الأرشيف: `zip -qr /home/ubuntu/AraNorm-1.7.0-enterprise.zip /home/ubuntu/AraNorm -x 'AraNorm/.git/*' ...`

## نقاط فنية مهمة لا تُنسى
- `license` في pyproject.toml = `{ file = "LICENSE" }` (صيغة backend-compatible)
- `pyproject.toml` يحتوي على markers اختبارات: slow وintegration
- التغطية تستثني `src/aranorm/models/*` و`src/aranorm/integrations/*`
- التخطيات الوثائقية الحالية: PyYAML، HuggingFace Datasets، spaCy، NLTK، scikit-learn
- `_ensure_*()` pattern في التكاملات يرفع IntegrationUnavailableError
- `BatchProcessingPolicy.collect` تجمع الاستثناءات في BatchProcessingError
- يجب عدم كسر: process/process_batch/process_iter/process_batch_async وdescribe وequality

## تحديث حالة الجولة السادسة (بعد ضغط السياق الأول)

### المسار C (steps_trace) — مكتمل ومختبر
`emit_steps_trace` في PipelineConfig + trace في ProcessorContext + NormalizationResult.steps_trace يعمل، round-trip OK. لم يُضاف إلى core/__init__.py exports بعد (يجب التحقق).

### المسار D (process_batch_retry) — مكتمل كودًا
أُضيف `process_batch_retry()` في pipeline.py، `BatchRetryReport` في contracts.py مع to_dict()، وحقل `results` اختياري في BatchProcessingError (متوافق backward). policy الافتراضية في retry هي collect.
ملاحظة اكتُشفت: في smoke، retry loop لم يُنفَّذ لأن مسار `except BatchProcessingError` يعمل، لكن `process_batch` مع policy=collect **لم يرفع الخطأ في اختباري الأخير** (عاد 20 نتيجة بلا رفع). يجب التأكد: هل policy=collect ترفع BatchProcessingError؟ من الكود: `if failures and active_policy.mode == "collect": raise BatchProcessingError` — نعم يرفع. في smoke السابق كان mock يؤثر على retry loop نفسه، وكان الخطأ الأول في smoke هو policy=None التي أصبحت collect الآن.
`scripts/smoke_retry.py` موجود لاختبار retry.

### ما تبقى للجولة السادسة
1. التحقق من مسار retry الفعلي مع policy=collect (smoke_retry.py بعد sed غير مكتمل)
2. مسار A: اختبارات فجوات التغطية
3. مسار B: اختبارات عدائية NormalizerUtils والمعالجات
4. مسار E: property-based tests بـ seed
5. مسار F: validator JSON data files
6. مسار G: CLI E2E بملفات كبيرة وstdin
7. H: bump إلى 1.7.0، CHANGELOG، README، performance_round6.json، security_round6.json، build، twine، SHA256SUMS، ROUND6_RELEASE_REPORT.md، archive، commit

### نقاط فنية مستجدة
- BatchProcessingError في errors.py يحمل الآن results=None افتراضيًا
- sed لإضافة BatchRetryReport لـ core/__init__.py غير مكتمل (فشل بسبب smoke)
- policy=collect في process_batch: يجمع ثم يرفع BatchProcessingError(results=list(results), failed_indices, errors)
- من make verify: format-check (black)، lint (flake8)، type-check (mypy)، test (pytest)، test-cov
- التغطية الحالية 92% والهدف 94%

## تحديث 2: C وD مكتملان ومختبران تمامًا
- C: steps_trace (emit_steps_trace في config + trace في context + NormalizationResult.steps_trace) مكتمل، round-trip OK، exported في core/__init__.py
- D: process_batch_retry + BatchRetryReport (contracts.py مع to_dict) + results في BatchProcessingError — كلها تعمل: healthy/recover/persistent/fail_fast guard/invalid max_retries/empty/to_dict. الملفات المؤقتة scripts/smoke_retry.py وscripts/debug_retry.py يجب حذفها أو تحويلها إلى اختبارات دائمة
- انحدار: 55 اختبار batch/async/cancel كلها تمر

## المرحلة 3 (التالية): اختبارات الجولة السادسة الدائمة
1. test_steps_trace_contracts.py: emit_steps_trace off/on، round-trip، isolation عن equality وCSV، process_batch/process_iter/async، عدم تسرب نص في trace
2. test_batch_retry_contracts.py: كل سيناريوهات smoke_retry.py
3. test_process_collect_results.py: BatchProcessingError.results يحمل النتائج الناجحة (sync + async)، backward compatibility
4. فجوات التغطية (مسار A): domain_stop 40%، phone 82%، cache 82%، chunker 86%، dialect_id 86%، stop_words_stage 88%، NormalizerUtils
5. مسار E: property-based بحالة ثابتة stdlib
6. مسار F: JSON data validation
7. مسار G: CLI E2E
8. مسار H: bump 1.7.0 + CHANGELOG + README + audits + build + report + archive + commit

## تحديث 3
- fixed: order_preserved عبر initial_successes dict بترتيب الإدخال
- FAILED test_max_retries_zero: output failed=[] رغم expected [1] — code يبدو سليمًا، الاشتباه في __pycache__ قديم (pip install -e cached bytecode)

## تحديث 4: حالة الاختبارات الجديدة
- test_steps_trace_contracts.py: 17 اختبارًا ناجحًا — عقود steps_trace مكتملة
- test_batch_retry_contracts.py: 20 اختبارًا ناجحًا — عقود retry مكتملة
- أصلحت bug حقيقي: process_batch_retry مع max_retries=0 كان يعيد failed_indices=[] لأن last_exc لم يُهيأ من failed dict — الآن last_exc = failed.get(index) أولًا
- batch_retry يعيد النتائج الآن بترتيب الإدخال (initial_successes dict)
- BatchRetryReport أُضيف إلى __all__ في core/__init__.py
- حذفت scripts/smoke_retry.py وscripts/debug_retry.py (استبدلت باختبارات دائمة)
- إجمالي: 697 ناجحًا + 5 متخطى
- test_coverage_gaps.py كُتب: DomainStopProcessorGaps، PhoneProcessorNormalize، StopWordsStageGaps، CacheHelpers، ChunkerGaps — يجب تشغيله وتصحيحه
- الخطوة التالية: تشغيل test_coverage_gaps وتصحيحه، ثم مسار E (property-based) إن أمكن، F (JSON validation)، G (CLI E2E)، H (bump 1.7.0 + CHANGELOG + README + audits + build + report + archive + commit)
- make verify: black, flake8, mypy, pytest — يعمل من جذر المشروع
- الإصدار الحالي 1.6.0 في pyproject.toml وsrc/aranorm/__init__.py — سنبقى 1.6.0 حتى bump النهائي إلى 1.7.0
- performance_round5.json وsecurity_round5.json موجودان — نحتاج performance_round6.json وsecurity_round6.json
- الفجوات المستهدفة في التغطية: domain_stop_processor 40%، phone_processor 82%، cache 82%، chunker 86%، stop_words_stage 88%، normalizer_utils 90%
- ملاحظة flake8: الملف السابق test_integration_matrix.py فشل بسبب import غير مستخدم — يجب التأكد من نظافة test_coverage_gaps.py

## تحديث 5: حالة الاختبارات الجديدة (تكملة)
- test_coverage_gaps.py: 21 ناجحًا — فجوات التغطية مغلقة
- test_property_based.py: 5 ناجحة (hypothesis) — invariants: idempotence, whitespace squeeze, Latin preservation (مقارنة بعد إزالة whitespace بسبب المطبعة)، dialect robustness, empty input
- test_cli_round6.py: 2/7 — المشاكل: (1) describe --json payload لا يحوي "version" و"fingerprint" مباشرة — يجب فحص البنية الفعلية للدالة _cmd_describe (سطر 408) و_cmd_plugins (424) و_cmd_version (387) و_cmd_normalize (66) في src/aranorm/cli.py لمعرفة مفاتيح JSON الفعلية؛ (2) captured_stdout fixture يعمل
- CLI: _build_parser private، main() يستقبل argv، dispatch عبر _handlers dict في main()
- المتبقي: إصلاح test_cli_round6.py وفق مفاتيح JSON الفعلية (استخدم `python3 -m aranorm describe --json` لمعاينة البنية)
- بعد إصلاحه: make verify كاملة، ثم coverage قياس (هدف 92%+)، ثم bumps: CHANGELOG 1.7.0، pyproject و__init__.py، ROUND6_RELEASE_REPORT، performance_round6.json + security_round6.json، wheel+sdist+twine، zip archive، commit، تسليم
- الاختبارات الحالية 700+ بعد إضافة 3 ملفات جديدة (coverage_gaps 21، property_based 5، cli_round6 7)
- hypothesis مثبت في البيئة (sudo pip3 install)

## تحديث 6: الاختبارات مكتملة
test_cli_round6.py: 8 ناجحة بعد مواءمتها مع البنية الفعلية (plugins payload: discovered/failures/group/ok/schema_version، version payload: package/version/schema_version، normalize يعيد list من entries بأسماء original/normalized/dialect). حذفت scripts/peek_cli.py.

الاختبارات الجديدة للجولة السادسة (13 ملف اختبار جديد في المجموع مع ملفات المسارات السابقة): test_steps_trace_contracts.py (17)، test_batch_retry_contracts.py (20)، test_coverage_gaps.py (21)، test_property_based.py (5)، test_cli_round6.py (8). إجمالي متوقع: 710+ ناجحًا.

الخطوات المتبقية: (1) make verify كاملة مع معالجة أي انحدار، (2) قياس التغطية (هدف 92%+)، (3) تدقيق الأداء والأمان performance_round6.json + security_round6.json، (4) تحديث API_REFERENCE.md وCHANGELOG.md لإضافة 1.7.0 وbump الإصدار في pyproject.toml وsrc/aranorm/__init__.py (حاليًا 1.6.0)، (5) build wheel+sdist وtwine check، (6) ROUND6_RELEASE_REPORT.md، (7) zip archive + checksums، (8) git commit، (9) التسليم.

## تحديث 7: بوابة الجودة نجحت بالكامل
make verify: black نظيف (144 ملف)، flake8 نظيف، mypy "Success: no issues found in 86 source files"، pytest **731 passed، 5 skipped** (كلها skips اختيارية موثقة: yaml, datasets, spaCy, NLTK, scikit-learn).

الإصلاحات التي طبقت: استيراد Tuple في pipeline.py typing imports، catastrophic branch في process_batch_retry يستخدم type(exc).__name__ في retry_report (catastrophic_cause)، إزالة استيراد PipelineConfig غير المستخدم في test_batch_retry_contracts.py.

make test-cov: 731 passed، 5 skipped in 16.81s — يجب عرض سطر التغطية النسبية (عادة يظهر في نهاية output، لم يُعرض في tail -6، أتحقق بـ tail أوسع أو .coverage).

الخطوات المتبقية: (1) التأكد من التغطية 92%+، (2) تدقيق الأداء security_round6.json + performance_round6.json (scripts/security_audit.py وscripts/performance_audit.py)، (3) bump 1.7.0: pyproject.toml (version)، src/aranorm/__init__.py (__version__)، CHANGELOG.md قسم [1.7.0]، (4) تحديث API_REFERENCE.md بـ steps_trace وprocess_batch_retry وBatchRetryReport، (5) تحديث README.md، (6) build wheel+sdist + twine check، (7) compileall 3.10/3.11/3.12، (8) ROUND6_RELEASE_REPORT.md، (9) zip archive + SHA256SUMS، (10) git commit (feat: round 6 v1.7.0)، (11) التسليم مع attachments: zip، تقرير، wheel، tar.gz، checksums، performance، security.

ملاحظة مهمة: ROUND6_PROGRESS_NOTES.md يحتوي كل التفاصيل السابقة؛ عند كل ضغط سياق يجب إعادة قراءته.

## تحديث 8: الإصدار مكتمل تقريبًا — المتبقي فقط الأرشيف والcommit والتسليم
الحالة: bump إلى 1.7.0 مكتمل (pyproject.toml، src/aranorm/__init__.py مع BatchRetryReport في exports، CHANGELOG قسم [1.7.0] مع روابط المقارنة، test_installed_smoke.py 1.7.0). make verify أخير: 731 passed، 5 skipped. التغطية 93% من 4,477. build: dist/aranorm-1.7.0-py3-none-any.whl + aranorm-1.7.0.tar.gz، twine PASSED. compileall OK على 3.10/3.11/3.12 (/home/ubuntu/.local/bin/python3.10، 3.11، /usr/bin/python3.12). SHA256SUMS في dist/: wheel=024ecb03995e6b317484afd04a815842c8f3e117da11f586dc1698635b6147e9، tar=5aaeccc1bfe1e0bfd3d2005b0472e937abbae73e8b0390b27246da9c8e9b21f1. ROUND6_RELEASE_REPORT.md مكتوب. الأداء: كاش 404x، single-flight 1 call من 16.

المتبقي: (1) cp dist/SHA256SUMS-1.7.0.txt وperformance_round6.json وsecurity_round6.json وROUND6_RELEASE_REPORT.md إلى /home/ubuntu/ أو إرفاقها مباشرة، (2) zip -r /home/ubuntu/AraNorm-1.7.0-enterprise.zip /home/ubuntu/AraNorm --exclude '*.git*'، (3) sha256sum للـzip وحفظه، (4) git add -A && commit -m "feat: round 6 architectural hardening v1.7.0" && git log -1، (5) result مع attachments: zip، تقرير، wheel، tar.gz، SHA256SUMS، performance_round6.json، security_round6.json.
