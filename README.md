# sds-hazard-crossref

Batch-processes Safety Data Sheet (SDS) PDFs, extracts every chemical
component listed, and cross-references each one against multiple public
regulatory and occupational exposure hazard lists (Cal/OSHA PELs, NIOSH
REL/IDLH, IARC/NTP carcinogen classifications, EPCRA 302/313, CalARP §5189
Appendix A, Cal/OSHA §339 Director's List, DTSC Candidate Chemicals, DOT
Hazmat Table, plus a check-only flag for ACGIH TLVs). Maintains a persistent
master component list across every SDS processed, tracking which products
contain each component and a human reviewer's disposition on ambiguous
matches.

This is the generalized, multi-list sibling of
[`prop65-sds-checker`](https://github.com/Ima-Hugestud/prop65-sds-checker),
which answers one focused question ("is this on Prop 65?"). This tool
answers the broader one: what hazard classifications, exposure limits, and
regulatory listings apply to everything in a chemical inventory, and which
products contain them.

**Status:** early scaffold. The shared SDS parsing layer (`parser_core`)
and the hazard-list plugin interface are in place; no hazard list plugins
are implemented yet. See `PROJECT_SPEC.md` and `DATA_SOURCES_REFERENCE.md`
for the full design and roadmap.

## Disclaimer

This tool assists hazard identification; it does not replace a qualified
EHS/industrial hygiene professional's judgment. List currency depends on
when the bundled or cached data was last refreshed — every report states
the "data as of" date for each list consulted, so a screening result is
always traceable to a specific data snapshot.

## Development

```
pip install -e ".[dev]"
pytest
```

Requires Python 3.10+. Runs identically on macOS, Windows, and Linux — no
OS-specific code paths, no shell-outs to platform-specific utilities, all
file paths via `pathlib.Path`.

## License

MIT — see `LICENSE`.
