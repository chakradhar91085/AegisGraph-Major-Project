"""Sensitivity exposure, the 5th risk signal."""
from app.security import exposure
from app.security.models import SignalValues
from app.security.risk import risk_engine


def test_ids_and_people_from_any_row_shape():
    rows = [{"emailId": "enron_1", "sender": "kenneth.lay@enron.com"}, {"email_id": "enron_2"}, {"count": 3}]
    assert exposure._ids_and_people(rows) == (["enron_1", "enron_2"], ["kenneth.lay@enron.com"])


def test_total_fades_with_half_life():
    half = exposure.settings.SECURITY_SENSITIVITY_HALF_LIFE_SECONDS
    assert exposure.accumulate(4.0, 1000.0, 1000.0 + half, 1.0) == 3.0


def test_signal_saturates():
    assert exposure.signal(0) == 0.0
    k = exposure.settings.SECURITY_SENSITIVITY_SCALE
    assert 0.63 < exposure.signal(k) < 0.64
    assert exposure.signal(10 * k) > 0.99


def test_exposure_raises_risk_alone():
    quiet = risk_engine.calculate_instantaneous_risk(SignalValues())
    exposed = risk_engine.calculate_instantaneous_risk(SignalValues(sensitivity_exposure=1.0))
    assert quiet == 0.0 and abs(exposed - 0.2) < 1e-9
