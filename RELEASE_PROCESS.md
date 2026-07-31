# Release Process

This document describes how to release a new version of AraNorm to PyPI.

---

## Prerequisites

- Write access to the GitHub repository
- PyPI account with maintainer access
- `build`, `twine`, `pre-commit` installed

---

## Release Checklist

### 1. Prepare the Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/v1.x.y
```

### 2. Update Version Number

Update the version in **two** places:

- `pyproject.toml`: `version = "1.x.y"`
- `src/aranorm/__init__.py`: `__version__ = "1.x.y"`

```bash
# Verify consistency
grep -r "1\.x\.y" pyproject.toml src/aranorm/__init__.py
```

### 3. Update CHANGELOG.md

Move entries from `[Unreleased]` to a new `[1.x.y] - YYYY-MM-DD` section.

Update the comparison links at the bottom of `CHANGELOG.md`.

### 4. Run the Full Test Suite

```bash
python -m pytest --tb=short -q
python -m flake8 src/aranorm/ --max-line-length=120
python -m mypy src/aranorm/ --ignore-missing-imports
```

All checks must pass with zero errors.

### 5. Build Distribution Artifacts

```bash
python -m build
# Produces:
#   dist/aranorm-1.x.y-py3-none-any.whl
#   dist/aranorm-1.x.y.tar.gz
```

### 6. Validate with Twine

```bash
twine check dist/aranorm-1.x.y*
```

Expected output: `PASSED` for both files.

### 7. Test Installation from Wheel

```bash
pip install dist/aranorm-1.x.y-py3-none-any.whl --force-reinstall
python -c "import aranorm; print(aranorm.__version__)"
aranorm version
python -m pytest tests/ -q --tb=short
```

### 8. Commit and Tag

```bash
git add pyproject.toml src/aranorm/__init__.py CHANGELOG.md
git commit -m "chore: bump version to 1.x.y"
git tag -a v1.x.y -m "Release v1.x.y"
```

### 9. Push and Open PR

```bash
git push origin release/v1.x.y
git push origin v1.x.y
```

Open a PR from `release/v1.x.y` → `main`. After approval and merge, proceed.

### 10. Upload to PyPI

```bash
# Test PyPI first (optional but recommended)
twine upload --repository testpypi dist/aranorm-1.x.y*

# Production PyPI
twine upload dist/aranorm-1.x.y*
```

### 11. Create GitHub Release

1. Go to [Releases](https://github.com/Alqudimi/AraNorm/releases/new)
2. Select tag `v1.x.y`
3. Copy the relevant section from `CHANGELOG.md` as the release notes
4. Attach the `.whl` and `.tar.gz` files
5. Publish

### 12. Post-Release

```bash
# Back on main, start [Unreleased] section
git checkout main
git pull origin main
# Add empty [Unreleased] section to CHANGELOG.md
```

---

## Versioning Policy

AraNorm follows [Semantic Versioning](https://semver.org/):

- **PATCH** (1.x.Y): Bug fixes, documentation updates, internal refactors with no API changes
- **MINOR** (1.Y.0): New features, new optional parameters, new processors — all backwards-compatible
- **MAJOR** (Y.0.0): Breaking changes to the public API

---

## Emergency Hotfix

```bash
git checkout v1.x.y
git checkout -b hotfix/v1.x.y+1
# apply fix
# update version to 1.x.y+1
# run tests
git tag -a v1.x.y+1
git push origin v1.x.y+1
twine upload dist/aranorm-1.x.y+1*
```
