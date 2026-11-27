# ملاحظات البحث والتدقيق الأولي — الجولة الثالثة

## مصادر خارجية

| المصدر | المبدأ المستخلص | أثره على AraNorm |
|---|---|---|
| [Python Packaging User Guide — Packaging Python Projects](https://packaging.python.org/en/latest/tutorials/packaging-projects/) | بنية `src/`، وجود `pyproject.toml` وREADME وLICENSE وtests، واستخدام backend/frontend لبناء wheel وsdist | AraNorm يستخدم `src/` و`pyproject.toml` بالفعل؛ يجب توسيع بوابة بناء/تثبيت معزول ونشر metadata دون كسر التوافق |
| [pytest — Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) | فصل `tests/` عن التطبيق، تشغيل الاختبارات ضد نسخة مثبتة، وتفضيل `--import-mode=importlib` للمشاريع الجديدة | يجب إضافة اختبار تثبيت مستقل، والتحقق من import mode/configuration، وفصل unit/integration/optional tests بوضوح |
| [pyOpenSci — Python Package Structure & Layout](https://www.pyopensci.org/python-package-guide/package-structure-code/python-package-structure.html) | `src/package` يقلل خطر اختبار ملفات العمل بدل النسخة المثبتة، ويفضل إبقاء الاختبارات والوثائق خارج الحزمة | البنية الحالية مناسبة؛ الأولوية ليست إعادة الهيكلة، بل إضافة حدود معمارية وعقود وطبقات اختبار فوق البنية القائمة |

## خط الأساس المحلي المعروف

الإصدار الحالي هو `1.3.0` على الفرع `professional-hardening`. الجولة السابقة أضافت `process_iter()`، `StreamingBatchExporter`، دعم streaming في CLI، وتقوية الكاش والتوثيق.

آخر تحقق معروف: **440 اختبارًا ناجحًا واختبار اختياري واحد متخطى** بسبب غياب `scikit-learn`، مع نجاح flake8 وmypy وBlack وبناء wheel وsdist وتثبيت wheel في بيئة معزولة.

## محاور التدقيق المقترحة

1. تحديد العقود العامة ومصادر التغيير في `pipeline`, `config`, `processors`, `stages`, `analysis`, `utils`, وCLI.
2. استخراج أي نقاط ضعف في الحدود المعمارية، إدارة الأخطاء، cancellation، الموارد، serialization، logging، والأمان.
3. إضافة بروتوكولات/واجهات صغيرة حيث تفيد، دون إعادة كتابة الوحدات القائمة.
4. فصل اختبارات الوحدة والتكامل والعقود والاختبارات الاختيارية واختبارات التثبيت، مع الحفاظ على التوافق.
5. إضافة قدرات تشغيلية مدروسة فقط إذا كانت قابلة للاختبار والتوثيق ولا تزيد التعقيد بلا عائد.
6. قياس الأداء والذاكرة قبل وبعد، وإعادة بناء artifacts واختبارها في بيئة نظيفة.

## مبدأ القرار

لن تُنفذ إعادة كتابة شاملة. كل تغيير يجب أن يكون موضعيًا، مبررًا بعقد أو اختبار أو قياس، ومحافظًا على الواجهات العامة إلا عند إضافة واجهة متوافقة وواضحة.
