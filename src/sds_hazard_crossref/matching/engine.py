"""
engine.py
The matching engine: turns a parsed `Component` into a `ResolvedComponent`
(the match key that will actually be used to query each hazard list
plugin), then runs that resolution against the plugin registry.

Implements PROJECT_SPEC.md Section 7 exactly:
  - CAS number is the primary match key, after normalization.
  - Name-based fallback only applies when CAS is absent, using the
    normalized name plus the curated synonym table.
  - CBI/trade-secret entries (no CAS, manufacturer withheld identity) are
    flagged "unresolvable — manual follow-up with supplier required."
    Never guessed.
  - A CAS number that's shape-valid but fails its checksum is NOT trusted
    as a match key (it could be an OCR error or a typo in the source SDS,
    and using it risks a wrong match against a list) — it falls back to
    name resolution instead, with a note flagging the checksum failure so
    a human reviewer sees it rather than it silently disappearing.
"""

from dataclasses import dataclass

from ..parser_core.cas import normalize_cas, is_valid_cas_checksum
from ..parser_core.names import normalize_name
from ..parser_core.composition import Component
from ..plugins.base import ListHit, HazardListPlugin
from .synonyms import SynonymTable


@dataclass
class ResolvedComponent:
    component: Component
    # "cas" | "name" | "unresolvable"
    match_key_type: str
    cas: str | None = None
    normalized_name: str | None = None
    note: str = ""


def resolve_component(
    component: Component, synonym_table: SynonymTable | None = None
) -> ResolvedComponent:
    """
    Determine the match key for one parsed component, per the priority
    order in PROJECT_SPEC.md Section 7.
    """
    if component.raw_cas:
        normalized = normalize_cas(component.raw_cas)
        if normalized and is_valid_cas_checksum(normalized):
            return ResolvedComponent(
                component=component, match_key_type="cas", cas=normalized
            )
        if normalized:
            # Shape-valid but checksum fails — don't trust it as the match
            # key; fall through to name resolution but flag the failure.
            name_result = _resolve_by_name(component, synonym_table)
            name_result.note = (
                f"CAS as disclosed ({component.raw_cas}) has an invalid "
                f"check digit — not used as a match key; resolved by name "
                f"instead. Flag for manual verification against the "
                f"source SDS." + (f" {name_result.note}" if name_result.note else "")
            ).strip()
            return name_result

    if component.disclosure_type == "trade_secret":
        return ResolvedComponent(
            component=component,
            match_key_type="unresolvable",
            note=(
                "Unresolvable — manufacturer withheld chemical identity as "
                "trade secret/CBI with no CAS disclosed. Manual follow-up "
                "with supplier required; no match key can be assigned "
                "without fabricating a CAS number."
            ),
        )

    return _resolve_by_name(component, synonym_table)


def _resolve_by_name(
    component: Component, synonym_table: SynonymTable | None
) -> ResolvedComponent:
    if not component.raw_name:
        return ResolvedComponent(
            component=component,
            match_key_type="unresolvable",
            note="No CAS number and no usable chemical name disclosed.",
        )

    if synonym_table:
        synonym_cas = synonym_table.lookup(component.raw_name)
        if synonym_cas:
            return ResolvedComponent(
                component=component,
                match_key_type="cas",
                cas=synonym_cas,
                note=(
                    f"No CAS disclosed on the SDS; resolved via curated "
                    f"synonym table (\"{component.raw_name}\" -> {synonym_cas})."
                ),
            )

    return ResolvedComponent(
        component=component,
        match_key_type="name",
        normalized_name=normalize_name(component.raw_name),
        note=(
            "No CAS disclosed and no synonym-table match; querying lists "
            "by normalized name only. Lower confidence than a CAS match — "
            "review before relying on a 'not listed' result."
        ),
    )


def check_against_lists(
    resolved: ResolvedComponent, plugins: list[HazardListPlugin]
) -> dict[str, ListHit]:
    """
    Query every plugin for one resolved component. An unresolvable
    component still gets an explicit ListHit per plugin (listed=False,
    match_method="unresolvable") rather than being silently skipped, so a
    report never shows a blank where a hazard determination should be —
    PROJECT_SPEC.md Section 8: "never present a 'not listed' result without
    making clear how current/confident that determination is."
    """
    hits: dict[str, ListHit] = {}
    for plugin in plugins:
        if resolved.match_key_type == "unresolvable":
            hits[plugin.list_id] = ListHit(
                list_id=plugin.list_id,
                listed=False,
                match_method="unresolvable",
                source_citation=plugin.display_name,
                data_as_of=plugin.data_as_of(),
                note=resolved.note,
            )
        else:
            hits[plugin.list_id] = plugin.lookup(resolved.cas, resolved.normalized_name)
    return hits
