# Changelog

All notable changes to this project are documented in this file. The format
loosely follows Keep a Changelog.

## [Unreleased]

### Added
- Initial repo scaffold: `pyproject.toml`, `.gitignore` (with the ACGIH
  local-file exclusion from day one), GitHub Actions CI matrix
  (ubuntu-latest / windows-latest / macos-latest).
- `parser_core`: SDS PDF text extraction, GHS section splitting, CAS number
  extraction/normalization/checksum validation, chemical name
  normalization. Generalized from `prop65-sds-checker`'s parsing layer.
- Hazard-list plugin interface (`HazardListPlugin`, `ListHit`) — no
  concrete list plugins implemented yet.
