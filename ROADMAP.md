# Roadmap

This document outlines the planned development direction for AraNorm. Items are subject to change based on community feedback and contributor availability.

---

## v1.3.0 — Q3 2025

### Core
- [ ] **`aranorm serve`** — lightweight HTTP server exposing the pipeline as a REST API
- [ ] **Config hot-reload** — reload `PipelineConfig` from file without restarting the server
- [ ] **GPU batch processing** — `process_batch_gpu()` using PyTorch DataLoader

### Processors
- [ ] **`DiacritizationProcessor`** — re-add diacritics using a neural model (opt-in, `[ml]` extra)
- [ ] **`SpellingCorrectionProcessor`** — statistical spelling correction for common MSA typos
- [ ] **`NumberNormalizationProcessor`** — normalize Arabic numeral words (واحد، اثنان…) to digits

### Analysis
- [ ] **`NamedEntityExtractor`** — rule-based NER for persons, locations, organizations
- [ ] **`TopicClassifier`** — TF-IDF based topic classification (news, social, legal, medical)

### Dialects
- [ ] **`HAJ`** — Hijazi dialect markers
- [ ] **`KHG`** — Khaleeji sub-dialect support
- [ ] Improved GLF/IRQ disambiguation

---

## v1.4.0 — Q4 2025

### Quality
- [ ] 100% type annotation coverage
- [ ] Property-based testing with Hypothesis
- [ ] Benchmarking suite with historical regression tracking

### Integrations
- [ ] **LangChain adapter** — `AranormChain` for use in LLM pipelines
- [ ] **spaCy pipeline component** — `nlp.add_pipe("aranorm")`
- [ ] **FastAPI middleware** — automatic Arabic text normalization in HTTP request bodies

### Infrastructure
- [ ] Docker image `ghcr.io/alqudimi/aranorm`
- [ ] GitHub Pages documentation site (Sphinx or MkDocs)
- [ ] PyPI trusted publisher setup

---

## v2.0.0 — 2026

### Breaking Changes (planned)
- Drop Python 3.9 support
- Replace `Union[Preset, str]` fields with strict `Preset` enum (string coercion in a separate constructor)
- Rename `handle_arabizi` → `convert_arabizi` for clarity

### New Architecture
- **Plugin system**: third-party processors via entry points
- **Pipeline serialization**: save/load entire configured pipelines to disk
- **Streaming API**: process arbitrarily large files without loading into memory

---

## How to Influence the Roadmap

Open an issue with the `enhancement` label and describe:
1. The use-case / problem you're solving
2. How you'd expect the API to look
3. Whether you're willing to contribute the implementation

Items with strong community support are prioritized.
