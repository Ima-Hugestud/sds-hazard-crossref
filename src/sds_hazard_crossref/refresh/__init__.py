"""
refresh \u2014 --refresh-data fetchers for automatable hazard-list sources.

Only sources confirmed genuinely automatable in DATA_SOURCES_REFERENCE.md
(bulk CSV or REST API, not just a searchable web page) get a fetcher here.
Hand-maintained sources (Cal/OSHA PEL, NIOSH, NTP, etc.) are versioned CSVs
in the plugin's own data, refreshed manually by a maintainer \u2014 see that
file's "Access Method" column for the reasoning per source.
"""

from .epcra_313_tri_fetch import FetchResult, TriFetchError, fetch_epcra_313_tri

__all__ = ["FetchResult", "TriFetchError", "fetch_epcra_313_tri"]
