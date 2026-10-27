from __future__ import annotations

from resolveai.suggestions.citations import validate_citations


def test_keeps_valid_citations_in_order_without_duplicates() -> None:
    check = validate_citations("Veja [2] e também [1]. De novo [2].", 3)
    assert check.cited_indices == (2, 1)
    assert check.removed == ()
    assert check.text == "Veja [2] e também [1]. De novo [2]."


def test_removes_citations_outside_retrieved_sources() -> None:
    check = validate_citations("Prazo de 3 dias [4]. Procedimento [1] [0].", 2)
    assert check.cited_indices == (1,)
    assert check.removed == (4, 0)
    assert check.text == "Prazo de 3 dias. Procedimento [1]."


def test_no_sources_means_no_citation_survives() -> None:
    check = validate_citations("Texto [1].", 0)
    assert check.cited_indices == ()
    assert check.text == "Texto."
