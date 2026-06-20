.PHONY: test lint docs docs-pdf

# Run the mocked unit suite (a dummy key satisfies module-level client construction).
test:
	GOOGLE_API_KEY=dummy-key uv run pytest -q

# Lint, including Google-style docstring rules on the core modules.
lint:
	uv run ruff check .

# Build the HTML documentation site (docs group; api ref from docstrings).
docs:
	uv run --group docs mkdocs build

# Build the navigable PDF (cover + clickable TOC + bookmarks) → site/ChainWatch-Documentation.pdf.
# Requires WeasyPrint system libs (libpango/cairo); see docs/README.md.
docs-pdf:
	ENABLE_PDF_EXPORT=1 uv run --group docs mkdocs build
