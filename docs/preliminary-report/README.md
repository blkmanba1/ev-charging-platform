# Project Specification and Preliminary Report (UESTCHN4008P)

Deliverable for the 30 October 2026 deadline: the six headings the Hainan template requires,
eight pages maximum, with the work plan on a single page.

| File | What it is |
| --- | --- |
| `preliminary-report.tex` | source, `article` + `ctex`, XeLaTeX only |
| `preliminary-report.pdf` | built output, 8 pages — the file that gets submitted, renamed to `2959485_Xu_UESTCHN4008P_Specification_Report_26-27.pdf` for the Moodle dropbox |
| `preliminary-report-bilingual.tex` / `.pdf` | 中文对照版 (10 pages): the same English text, each paragraph followed by its Chinese translation in grey. Reading copy for the author and for explaining the work in Chinese; **not** the submission |
| `plan/gantt.xlsx` | the work plan as an editable workbook: `Work plan` (this sub-project, the sheet the PDF carries), `Group overview` (all five sub-projects, for group planning), `Milestones` |
| `plan/make_gantt.py` | regenerates the workbook from the sub-project definitions in this repository |
| `plan/gantt.png` | the chart as rendered for the PDF |

## Build

```bash
xelatex preliminary-report.tex
bibtex  preliminary-report
xelatex preliminary-report.tex
xelatex preliminary-report.tex
```

The bilingual copy builds the same way from `preliminary-report-bilingual.tex`. It is a second
document rather than a translation layer, so editing the submission means editing both files; that
is deliberate, because the two are allowed to diverge (the Chinese one carries the explanatory
asides that must not appear in a submission, such as why the Gantt shows only one sub-project).

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

`make_gantt.py` carries the content. The `Work plan` sheet is the one the PDF shows: the five main
tasks of the FYP task book, each broken into sub-tasks, because the handbook asks for "sub-tasks
under the main tasks already specified by your Supervisor" and requires the plan as a Gantt sheet
(p12). The other sub-projects appear there only as grey external dependencies, since p13 states
that in a shared project the supervisor allocates **individual** work packages — a student's plan
should not schedule other people's work. The `Group overview` sheet keeps the five-track view for
group discussions; the status column in both records what exists on 24 October 2026 rather than what
is hoped for.

## Constraints that shaped the document

- Eight pages is a hard limit in the template; the page count is checked with `pdfinfo`.
- The literature review must run two to three pages, so it is condensed from the seven-page
  standalone review rather than copied.
- The work plan must fit on one page, which is why `\clearpage` puts section 6 on its own page with
  the task table and the Gantt together.
- Section 3 states objectives with dates and measures, and records which of them are already met,
  because two of the four were reached in Phase 1.
