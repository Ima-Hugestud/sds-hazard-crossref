# Test fixtures — not production data

Everything in this directory exists to exercise parsing/matching logic in
tests. None of it is a real, complete, or currently-accurate extract of any
regulatory list.

`epcra_313_tri_TEST_FIXTURE.csv` — a handful of long-standing, unambiguous
EPA TRI chemical list entries (toluene, benzene, formaldehyde, methanol),
plus one category-level entry with no CAS to exercise that code path. The
real TRI list covers 800+ chemicals and chemical categories and changes
over time (see PROJECT_SPEC.md / DATA_SOURCES_REFERENCE.md row 8) — this
file is not that list, and `EPCRATriPlugin` never ships with a bundled
"real" default for this reason. Production data must come from EPA's
actual bulk CSV or Envirofacts API via a `--refresh-data` command (not yet
implemented).
