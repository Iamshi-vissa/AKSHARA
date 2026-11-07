# End-to-end checks

`phase1.e2e.mjs` drives the real application in Chromium (Playwright): register, upload real
DOCX/PDF/PPTX files, verify the downloaded original is byte-identical (SHA-256), check that a
`.docm` file is refused, that unbuilt modules are shown as locked, that the refresh cookie is
httpOnly and invisible to JavaScript, and that the layout has no horizontal scroll at phone width.

```bash
node e2e/phase1.e2e.mjs path/to/samples [path/to/screenshots]
```

The samples folder needs `Research_Report.docx`, `Methodology_Paper.pdf`,
`Quarterly_Review.pptx` and `Thesis.docm` (any DOCX renamed). Set `AKSHARA_WEB_URL` to test
the Docker stack (`http://localhost:8080`); the default is the Vite dev server.
