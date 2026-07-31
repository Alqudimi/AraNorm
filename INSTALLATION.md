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
