"""MASK mode must hide real person names now that the graph stores them."""
from app.security.masking import mask_text, names_from_records


def test_names_come_from_name_columns_only():
    rows = [{"sender_name": "Kenneth L. Lay", "sender": "kenneth.lay@enron.com", "subject": "Board Meeting Today"},
            {"name": "Rosalee Fleming", "count": 3}, {"name": "Cher"}]
    assert names_from_records(rows) == {"Kenneth L. Lay", "Rosalee Fleming"}


def test_masks_name_forms():
    names = {"Kenneth L. Lay"}
    for text in ["Kenneth L. Lay wrote", "Kenneth Lay wrote", "Lay, Kenneth L. wrote", "kenneth lay wrote"]:
        assert mask_text(text, names) == "[REDACTED_NAME] wrote", text


def test_leaves_other_words_alone():
    assert mask_text("Kenneth was late; Lay off the coffee", {"Kenneth Lay"}) == "Kenneth was late; Lay off the coffee"
