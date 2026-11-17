# reference/ — In-House BRD Sample

This folder holds the **in-house BRD sample** that users can preview and
download from the "Sample BRD" button in the top bar.

## Files

| File | Purpose |
|------|---------|
| `House_Sample_BRD.docx` | The finished in-house BRD (place here once you have it) |
| `House_Sample_BRD.pdf`  | Optional pre-exported PDF for faster preview. If missing, the app auto-converts the .docx on first request (requires `docx2pdf` or LibreOffice). |

## How it works

1. Place your completed in-house BRD at `reference/House_Sample_BRD.docx`.
2. *(Optional)* Export it to PDF from Word and save as `reference/House_Sample_BRD.pdf`.
   This gives the fastest and most accurate preview (no conversion needed).
3. If only the `.docx` is present the platform will attempt to convert it to PDF
   automatically on the first request, using `docx2pdf` (Windows/macOS) or
   LibreOffice (Linux).  The resulting PDF is cached next to the `.docx` and
   regenerated automatically whenever the `.docx` is updated.
4. If no converter is available the preview falls back to an approximate HTML
   render (via `mammoth`) with a banner explaining that it is not pixel-perfect.
5. Users can always download the `.docx` directly to see the exact layout.

## People lookup (`data/users.xlsx`)

The `data/` folder (at the project root, not here) may contain a `users.xlsx`
spreadsheet.  At application start, if this file is newer than `data/users.db`,
it is imported automatically.  You can also trigger the import manually:

```
python import_users.py data/users.xlsx
```

Expected columns (case-insensitive, order does not matter):
- **Name** (or "Full Name", "Employee Name")
- **Email** (or "E-Mail", "Mail ID")
- **Designation** (or "Title", "Role")
- **Department** (or "Dept", "Function")

Separate first-name / last-name columns are also accepted and will be joined.
