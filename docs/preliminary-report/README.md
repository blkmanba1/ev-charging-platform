# Project Specification and Preliminary Report (UESTCHN4008P)

Deliverable for the 30 October 2026 deadline: the six headings the Hainan template requires,
eight pages maximum, with the work plan on a single page.

| File | What it is |
| --- | --- |
| `preliminary-report.tex` | source, `article` + `ctex`, XeLaTeX only |
| `preliminary-report.pdf` | built output, 8 pages |
| `plan/gantt.xlsx` | the Gantt chart as an editable workbook (two sheets: `Gantt`, `Milestones`) |
| `plan/make_gantt.py` | regenerates the workbook from the sub-project definitions in this repository |
| `plan/gantt.png` | the chart as rendered for the PDF |

## Build

```bash
xelatex preliminary-report.tex
bibtex  preliminary-report
xelatex preliminary-report.tex
xelatex preliminary-report.tex
```

Bibliography resolves through `../literature-review/references.bib`, so the twenty references in
this report are the same verified entries as the literature review rather than a second list.
The forecast figure is taken from `../phase1-report/figures/`, so the numbers and the picture come
from the same pipeline run.

## Regenerating the Gantt

```bash
cd plan && python make_gantt.py          # writes gantt.xlsx
```

Then export the `Gantt` sheet to PDF from Excel and rasterise it:

```powershell
$ws.ExportAsFixedFormat(0, "gantt.pdf")
pdftoppm -r 300 -png -singlefile gantt.pdf gantt_raw
# crop the white margin, then save as gantt.png at 300 dpi
```

`make_gantt.py` carries the content: five sub-project tracks plus six milestones. The work packages
are the ones the repository defines in `subprojects/*/README.md`, the edges are the ones
`docs/integration-contract.md` fixes, and the status column records what exists on 24 October 2026
rather than what is hoped for.

## Constraints that shaped the document

- Eight pages is a hard limit in the template; the page count is checked with `pdfinfo`.
- The literature review must run two to three pages, so it is condensed from the seven-page
  standalone review rather than copied.
- The work plan must fit on one page, which is why `\clearpage` puts section 6 on its own page with
  the task table and the Gantt together.
- Section 3 states objectives with dates and measures, and records which of them are already met,
  because two of the four were reached in Phase 1.
