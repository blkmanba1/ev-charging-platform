# Literature review — build notes

`literature-review.tex` is the source; `literature-review.pdf` is the deliverable.
`references.bib` holds the 21 references, transcribed from their Crossref deposit records.

## Build

```bash
cd docs/literature-review
xelatex -interaction=nonstopmode literature-review.tex   # first pass
bibtex literature-review                                 # resolve \cite
xelatex -interaction=nonstopmode literature-review.tex   # second pass
xelatex -interaction=nonstopmode literature-review.tex   # third, so refs settle
```

BibTeX must run between passes, otherwise every `\cite` prints as `[?]`.

## Verify

```bash
pdfinfo literature-review.pdf | grep Pages              # expect 7
grep -c 'Overfull \\hbox' literature-review.log         # expect 0
grep -n '^! ' literature-review.log                     # expect no output
grep -n 'Citation .* undefined' literature-review.log   # expect no output
grep -c 'Warning' literature-review.blg                 # expect 0
pdftotext -layout literature-review.pdf - | grep -c 'doi:10\.'   # expect 21
```

The last check matters: the standard `unsrt` bibliography style silently drops the `doi` field, so
each entry also carries the DOI in its `note` field, which `unsrt` does print. If an entry ever gains
a second `note`, BibTeX keeps only the first and logs `ignoring ... extra "note" field` — check the
`.blg` for that warning rather than trusting the page count.

## Provenance of the references

Each reference is `VERIFIED`: its DOI resolved through Crossref with matching title, authors, year and
venue. Publishers returning 403 or a bot challenge to automated fetches (MDPI, IEEE, Nature,
ScienceDirect) were checked through the Crossref or OpenAlex deposit record instead; no abstract was
taken from a search snippet. The survey notes, including three references dropped for unobtainable
abstracts, one DOI that does not resolve, and one that resolves to an unrelated topic, are in
`data/raw/literature-research.md` (git-ignored).

## House rules applied

- Academic register, no meta-narrative about how the document was produced (workspace `G-S-11`),
  verified by searching the built PDF text for the banned patterns.
- LaTeX compiled with `xelatex` (workspace report rule).
- Built artefacts (`*.aux`, `*.log`, `*.out`, `*.bbl`, `*.blg`) are git-ignored; only `references.bib`,
  the `.tex`, this file and the `.pdf` are committed.
