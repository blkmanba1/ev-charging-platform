"""Build the project Gantt chart as an .xlsx workbook.

Content is derived from what the repository actually defines, not from imagination:
  subprojects/sp1..sp5/README.md   -> owners, work packages, dependencies
  docs/integration-contract.md     -> what each sub-project consumes and produces
  the SP1 Phase-1 results          -> which bars are already done

Run:  python make_gantt.py
Output: gantt.xlsx in the same directory.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

HERE = Path(__file__).resolve().parent

MONTHS = ["Sep-26", "Oct-26", "Nov-26", "Dec-26", "Jan-27",
          "Feb-27", "Mar-27", "Apr-27", "May-27", "Jun-27"]

# (owner label, colour, (task, start index, end index, status))
GROUPS = [
    ("SP1  Data & forecasting", "2F6F9F", [
        ("Data sourcing, licence check, dataset register", 0, 1, "Done"),
        ("Session-to-hourly demand pipeline", 0, 1, "Done"),
        ("Features, direct multi-horizon models, 25-origin backtest", 1, 2, "Done"),
        ("Cross-site validation, Palo Alto, no retuning", 2, 2, "Done, 0.549 vs 0.670"),
        ("Contract export and integration with SP2/SP4/SP5", 2, 4, "In progress"),
        ("Interim report and presentation", 3, 4, "Draft"),
        ("Phase-3 evaluation support", 5, 7, "Planned"),
        ("Dissertation and final poster", 5, 8, "Planned"),
    ]),
    ("SP2  Smart scheduling", "C0863B", [
        ("Tariff sources and cost model (issue #2)", 1, 2, "Sources verified, table pending"),
        ("Scheduler build: LP / heuristic against valley filling", 2, 3, "Planned"),
        ("Uncontrolled versus scheduled comparison", 3, 4, "Planned"),
        ("Phase-3 scenarios with SP1", 5, 6, "Planned"),
    ]),
    ("SP3  Renewable-aware", "7A7A7A", [
        ("Owner allocation and dataset decision", 4, 5, "Unallocated - risk"),
        ("Solar forecast module, ERA5 / NASA POWER", 6, 7, "Planned, at risk"),
    ]),
    ("SP4  Dashboard", "4E8B57", [
        ("Initial dashboard script (on fork, not merged)", 0, 1, "On fork, 99 lines"),
        ("Wire the contract files, replace placeholder columns", 3, 4, "Planned"),
        ("Views, integration test, reporting", 6, 7, "Planned"),
    ]),
    ("SP5  System assessment", "7B5EA7", [
        ("Cost and carbon-intensity baseline for both sites", 1, 2, "Not started"),
        ("Savings, emissions and benchmarking", 5, 7, "Planned"),
        ("Final assessment report for the dashboard", 7, 8, "Planned"),
    ]),
]

MILESTONES = [
    ("Project Specification & Preliminary Report", 1, "30 Oct 2026"),
    ("Interim Report", 4, "8 Jan 2027"),
    ("Interim Presentation", 4, "11-22 Jan 2027"),
    ("Final Poster", 7, "19-21 Apr 2027"),
    ("Final Dissertation", 7, "30 Apr 2027"),
    ("Project end (task book)", 9, "1 Jul 2027"),
]

THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
TASK_FONT = Font(name="Calibri", size=10)
OWNER_FONT = Font(name="Calibri", size=10, bold=True)
STATUS_FONT = Font(name="Calibri", size=9, italic=True, color="404040")
MONTH_FILL = PatternFill("solid", fgColor="F2F2F2")


def build() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Gantt"
    ws.sheet_view.showGridLines = False

    last_col = get_column_letter(11)  # K

    ws.merge_cells(f"A1:{last_col}1")
    c = ws["A1"]
    c.value = "Design and Development of an AI-Enabled Smart EV Charging and Energy Management Platform"
    c.font = Font(name="Calibri", size=14, bold=True, color="1F3864")
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22

    ws.merge_cells(f"A2:{last_col}2")
    c = ws["A2"]
    c.value = ("Project Gantt, September 2026 to June 2027  |  baseline of 24 October 2026  |  "
               "work packages derived from the repository (subprojects/*/README.md, "
               "docs/integration-contract.md)")
    c.font = Font(name="Calibri", size=9, italic=True, color="404040")
    ws.row_dimensions[2].height = 14

    # header row 4
    heads = ["Sub-project", "Work package"] + MONTHS + ["Status, 24 Oct 2026"]
    for j, h in enumerate(heads, start=1):
        cell = ws.cell(row=4, column=j, value=h)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center" if j > 2 else "left",
                                   vertical="center", wrap_text=True)
    ws.row_dimensions[4].height = 26

    row = 5
    for owner, colour, tasks in GROUPS:
        fill = PatternFill("solid", fgColor=colour)
        start_row = row
        for task, s, e, status in tasks:
            ws.cell(row=row, column=1, value=owner).font = OWNER_FONT
            ws.cell(row=row, column=2, value=task).font = TASK_FONT
            ws.cell(row=row, column=2).alignment = Alignment(vertical="center", wrap_text=True)
            for k in range(len(MONTHS)):
                cell = ws.cell(row=row, column=3 + k)
                cell.border = BORDER
                if s <= k <= e:
                    cell.fill = fill
            ws.cell(row=row, column=13, value=status).font = STATUS_FONT
            ws.cell(row=row, column=13).alignment = Alignment(vertical="center")
            for j in (1, 2, 13):
                ws.cell(row=row, column=j).border = BORDER
            ws.row_dimensions[row].height = 26
            row += 1
        # one label per sub-project, not one per row
        ws.merge_cells(start_row=start_row, start_column=1, end_row=row - 1, end_column=1)
        owner_cell = ws.cell(row=start_row, column=1)
        owner_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # milestone block
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    c = ws.cell(row=row, column=1, value="Milestones (programme handbook)")
    c.font = Font(name="Calibri", size=10, bold=True, color="1F3864")
    row += 1
    for name, idx, date in MILESTONES:
        ws.cell(row=row, column=2, value=name).font = TASK_FONT
        ws.cell(row=row, column=2).alignment = Alignment(vertical="center")
        ws.cell(row=row, column=2).border = BORDER
        ws.cell(row=row, column=1).border = BORDER
        for k in range(len(MONTHS)):
            cell = ws.cell(row=row, column=3 + k)
            cell.border = BORDER
            if k == idx:
                cell.value = "\u25c6"
                cell.font = Font(name="Calibri", size=11, bold=True, color="C00000")
                cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=row, column=13, value=date).font = STATUS_FONT
        ws.cell(row=row, column=13).border = BORDER
        ws.row_dimensions[row].height = 20
        row += 1

    # legend / notes
    row += 1
    notes = [
        "Reading the chart: a filled cell marks a month in which the work package is active.",
        "Owners are taken from the sub-project READMEs; SP3 is still unallocated and is shown as a risk.",
        "SP1 bars marked Done are evidenced by the merged pipeline, the 77 passing tests and the Phase-1 report.",
        "SP4's September bar records an initial dashboard script that exists only on a fork, not in the main repository.",
        "Consumers and producers of every arrow are fixed in docs/integration-contract.md.",
    ]
    for n in notes:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=13)
        c = ws.cell(row=row, column=1, value=n)
        c.font = Font(name="Calibri", size=9, color="404040")
        c.alignment = Alignment(vertical="center")
        row += 1

    widths = {"A": 22, "B": 46, "K": 26, "M": 26}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    for k in range(len(MONTHS)):
        ws.column_dimensions[get_column_letter(3 + k)].width = 8.5

    ws.freeze_panes = "C5"

    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)

    # second sheet: milestone register
    ms = wb.create_sheet("Milestones")
    ms.sheet_view.showGridLines = False
    ms.append(["Date", "Milestone", "Weight / note"])
    for j in range(1, 4):
        cell = ms.cell(row=1, column=j)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.border = BORDER
    rows = [
        ("30 Oct 2026", "Project Specification & Preliminary Report", "10% of the final mark"),
        ("8 Jan 2027", "Interim Report", "assessed"),
        ("11-22 Jan 2027", "Interim Presentation", "window set by the school"),
        ("19-21 Apr 2027", "Final Poster", "assessed"),
        ("30 Apr 2027", "Final Dissertation", "main submission"),
        ("1 Jul 2027", "Project end", "task-book end date"),
    ]
    for r in rows:
        ms.append(list(r))
    for r in range(2, 2 + len(rows)):
        for j in range(1, 4):
            ms.cell(row=r, column=j).font = TASK_FONT
            ms.cell(row=r, column=j).border = BORDER
    for col, w in {"A": 16, "B": 44, "C": 26}.items():
        ms.column_dimensions[col].width = w

    return wb


if __name__ == "__main__":
    out = HERE / "gantt.xlsx"
    build().save(out)
    print("written", out)
