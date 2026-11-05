"""The risk formula: ordinary use stays allowed; probing climbs to mask and block."""
from app.security.models import QueryRecord, SignalValues
from app.security.policy import policy_engine
from app.security.risk import risk_engine
from app.security.signals import signals_calculator as sig


def rec(t, *people):
    return QueryRecord(timestamp=t, query="q", entities=list(people))


def smoothed(signal_list):
    risk = 0.0
    for s in signal_list:
        risk = risk_engine.calculate_ewma(risk_engine.calculate_instantaneous_risk(s), risk)
    return risk


def mode(risk):
    return policy_engine.calculate_policy(risk).response_mode.value


def test_no_signals_means_no_risk():
    assert risk_engine.calculate_instantaneous_risk(SignalValues()) == 0.0


def test_one_strong_signal_counts_and_signals_compound():
    one = risk_engine.calculate_instantaneous_risk(SignalValues(sensitivity_exposure=1.0))
    two = risk_engine.calculate_instantaneous_risk(SignalValues(sensitivity_exposure=1.0, entity_focus=1.0))
    assert one == 0.6
    assert one < two < 1.0


def test_unrelated_questions_have_no_topic_focus_and_repeats_do():
    assert sig.calculate_semantic_focus([[1.0, 0.0], [0.1, 0.995]]) == 0.0
    assert sig.calculate_semantic_focus([[1.0, 0.0], [1.0, 0.0]]) == 1.0
    assert sig.calculate_semantic_focus([[1.0, 0.0]]) == 0.0


def test_rate_counts_recent_queries_only():
    history = [rec(0), rec(1000), rec(1090)]
    assert sig.calculate_temporal_frequency([], 1100) == 0.0
    assert sig.calculate_temporal_frequency(history, 1100) == 2 / 20


def test_entity_focus_counts_queries_not_rows():
    assert sig.calculate_entity_focus([rec(0, "a", "b", "c", "d", "e")]) == 0.0
    assert sig.calculate_entity_focus([rec(0, "a", "a", "a")]) == 0.0
    assert sig.calculate_entity_focus([rec(t, "a") for t in range(5)]) == 1.0


def test_footprint_is_zero_without_rows():
    assert sig.calculate_graph_footprint("agent_query", 0) == 0.0
    assert sig.calculate_graph_footprint("agent_query", 25) == 0.5
    assert sig.calculate_graph_footprint("agent_query", 500) == 1.0


def test_ordinary_session_stays_allowed():
    ordinary = SignalValues(temporal_frequency=0.2, entity_focus=0.25, graph_footprint=0.2, sensitivity_exposure=0.05)
    assert mode(smoothed([ordinary] * 10)) == "ALLOW"


def test_probing_climbs_through_mask_to_block():
    probe = SignalValues(semantic_focus=0.9, entity_focus=0.75, temporal_frequency=0.2,
                         graph_footprint=0.2, sensitivity_exposure=0.9)
    assert mode(smoothed([probe])) == "MASK"
    assert mode(smoothed([probe] * 3)) == "BLOCK"


def test_focus_without_sensitive_data_is_never_blocked():
    researcher = SignalValues(semantic_focus=1.0, entity_focus=1.0, temporal_frequency=0.25,
                              graph_footprint=0.2, sensitivity_exposure=0.15)
    assert mode(smoothed([researcher] * 20)) == "MASK"


def test_repeating_a_name_is_not_counted_twice():
    both = risk_engine.calculate_instantaneous_risk(SignalValues(semantic_focus=1.0, entity_focus=1.0))
    assert both == risk_engine.calculate_instantaneous_risk(SignalValues(entity_focus=1.0))


def test_innocent_queries_lower_risk_slowly():
    probe = SignalValues(semantic_focus=1.0, entity_focus=1.0, sensitivity_exposure=1.0)
    high = smoothed([probe] * 3)
    assert risk_engine.calculate_ewma(0.0, high) > high * 0.75
