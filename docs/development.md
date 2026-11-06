# Development

```bash
git clone https://github.com/industrial-mathematics-group/aisignoff
cd aisignoff
pip install -e . pytest
pytest
aisignoff lint      # the tool declares its own files, too (see SIGNOFF.toml)
```

Contributions follow the [contributing guidelines](https://github.com/industrial-mathematics-group/.github/blob/main/.github/CONTRIBUTING.md) of the Industrial Mathematics Group, including the AI declaration in each pull request. Update `SIGNOFF.toml` in the same pull request when a change alters how a file was created or reviewed.

## Documentation

The documentation is built with [MkDocs](https://www.mkdocs.org) and the [Material theme](https://squidfunk.github.io/mkdocs-material/), from the Markdown files in `docs/` and the page list in `mkdocs.yml`.

```bash
pip install -r docs/requirements.txt
mkdocs serve          # preview at http://127.0.0.1:8000, reloads on every change
mkdocs build --strict # what CI runs: fails on broken links
```

The *Docs* workflow builds the site on every pull request and publishes it to GitHub Pages on every push to `main`.

## Releasing

1. Bump the version in `pyproject.toml`, `src/aisignoff/__init__.py` and `uv.lock`.
2. Publish a GitHub release with the tag `vX.Y.Z`.

The *Publish to PyPI* workflow checks that the tag matches the version, runs the tests, builds the package and uploads it through PyPI's trusted publishing. No token is stored in the repository.
