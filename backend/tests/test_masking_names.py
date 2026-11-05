"""MASK mode must hide real person names now that the graph stores them."""
from app.security.masking import mask_graph, mask_text, names_from_records


def test_names_come_from_name_columns_only():
    rows = [{"sender_name": "Kenneth L. Lay", "sender": "kenneth.lay@enron.com", "subject": "Board Meeting Today"},
            {"name": "Rosalee Fleming", "count": 3}, {"name": "Cher"}]
    assert names_from_records(rows) == {"Kenneth L. Lay", "Rosalee Fleming"}


def test_names_inside_nested_lists_are_found():
    rows = [{"themes": ["Gas Power Trading"], "top_people": [{"name": "Jeff Dasovich", "sent": 5504}], "names": ["Kay Mann"]}]
    assert names_from_records(rows) == {"Jeff Dasovich", "Kay Mann"}


def test_masked_graph_details_keep_no_free_text():
    graph = {"nodes": [
        {"id": "enron_1", "label": "Board", "type": "Email", "details": {
            "sender": "Kenneth Lay", "body": "Call Kenneth", "score": 0.8, "sensitivity": ["Legal"]}},
        {"id": "Kenneth Lay", "label": "Kenneth Lay", "type": "Person", "details": {"title": "CEO", "sent": 12}},
    ], "edges": []}
    email, person = mask_graph(graph)["nodes"]
    assert email["details"] == {"score": 0.8, "sensitivity": ["Legal"]}
    assert person["details"] == {"sent": 12}


def test_masks_name_forms():
    names = {"Kenneth L. Lay"}
    for text in ["Kenneth L. Lay wrote", "Kenneth Lay wrote", "Lay, Kenneth L. wrote", "kenneth lay wrote"]:
        assert mask_text(text, names) == "[REDACTED_NAME] wrote", text


def test_leaves_other_words_alone():
    assert mask_text("Kenneth was late; Lay off the coffee", {"Kenneth Lay"}) == "Kenneth was late; Lay off the coffee"
