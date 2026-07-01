# Test fixtures — not production data

Everything in this directory exists to exercise parsing/matching logic in
tests. None of it is a real, complete, or currently-accurate extract of any
regulatory list.

`epcra_313_tri_TEST_FIXTURE.csv` — a handful of long-standing, unambiguous
EPA TRI chemical list entries (toluene, benzene, formaldehyde, methanol),
one true-blank-CAS category entry to exercise that defensive path, and one
real category-code entry ("Antimony compounds" / code N010, confirmed
against a live EPA API response) to exercise category-name matching. The
real TRI list covers 800+ chemicals and chemical categories and changes
over time (see PROJECT_SPEC.md / DATA_SOURCES_REFERENCE.md row 8) — this
file is not that list, and `EPCRATriPlugin` never ships with a bundled
"real" default for this reason. Production data comes from EPA's actual
bulk CSV or Envirofacts API via `sds-crossref-refresh-data`.
