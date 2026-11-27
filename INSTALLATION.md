# Installation

## Requirements

- Python **3.9** or higher
- pip 21.0 or higher (for PEP 517 support)

---

## Basic Installation

```bash
pip install aranorm
```

The core package has **zero mandatory runtime dependencies**. After installation you can immediately normalize Arabic text.

---

## Optional Extras

### CAMeL Tools Integration (model-based dialect identification, >90% accuracy)

```bash
pip install "aranorm[camel]"
```

Requires `camel-tools >= 1.5.0`. Provides model-level dialect identification using the MADAR corpus.

### Machine Learning / Transformers (neural CODA and MSA normalization)

```bash
pip install "aranorm[ml]"
```

Requires `transformers`, `torch`, and `sentencepiece`. Provides neural sequence-to-sequence normalization.

### Full Installation (everything)

```bash
pip install "aranorm[full]"
```

Installs all optional dependencies including `pyarabic`, `tnkeeh`, `emoji`, `regex`, and `tqdm`.

### Development Installation

```bash
git clone https://github.com/Alqudimi/AraNorm.git
cd AraNorm
pip install -e ".[dev,quality]"
```

---

## Verify Installation

```bash
# Check version
aranorm version

# Quick normalization test
aranorm normalize "أهلاً وسهلاً"

# Run the demo
python demo.py
```

### Optional HTTP service

The standard-library HTTP adapter is opt-in and adds no mandatory dependency. Bind it to loopback for local use or place it behind a trusted production gateway that provides TLS termination, authentication, authorization, rate limiting, and access logging:

```bash
aranorm serve --host 127.0.0.1 --port 8765 --preset standard
aranorm serve --config pipeline.json --reload-interval 1.0 --body-limit 2000000
```

The adapter exposes `/health/live`, `/health/ready`, `/v1/normalize`, `/v1/batch`, and `/v1/describe`. It enforces JSON input and a bounded request body, but it is not a substitute for an internet-facing security gateway. Configuration reload is optional; invalid updates preserve the last valid pipeline snapshot and report a degraded health state.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'aranorm'`

Ensure you installed into the correct Python environment:

```bash
python -c "import aranorm; print(aranorm.__version__)"
```

### CAMeL Tools installation fails

CAMeL Tools has platform-specific build requirements. On Linux/macOS:

```bash
pip install camel-tools
```

On Windows, you may need the Microsoft C++ Build Tools.

### Torch installation is slow

Use the CPU-only torch wheel for faster installation when GPU is not needed:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "aranorm[ml]"
```

---

## Upgrading

```bash
pip install --upgrade aranorm
```

After upgrading, check [CHANGELOG.md](CHANGELOG.md) for breaking changes.

---

## Uninstalling

```bash
pip uninstall aranorm
```
