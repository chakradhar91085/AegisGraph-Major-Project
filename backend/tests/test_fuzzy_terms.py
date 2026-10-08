from app.retrieval.strategies import fuzzy_search_terms


def test_every_word_required_with_typo_allowance_by_length():
    assert fuzzy_search_terms("Christopher Calgar") == "+christopher~ +calgar~"
    assert fuzzy_search_terms("Ken Lai") == "+ken~1 +lai~1"
    assert fuzzy_search_terms("J. Li") == "+li"


def test_lucene_syntax_is_stripped():
    assert fuzzy_search_terms('calger" OR *:*') == "+calger~ +or"
    assert fuzzy_search_terms("?!") == ""
