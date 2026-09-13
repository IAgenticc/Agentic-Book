from document_intelligence.risk import DocumentMetadata, classify_risk


def test_low_risk_when_nothing_sensitive():
    assert classify_risk(DocumentMetadata()) == "low"


def test_medium_risk_when_contains_pii():
    assert classify_risk(DocumentMetadata(contains_pii=True)) == "medium"


def test_high_risk_when_crosses_data_boundary():
    assert classify_risk(DocumentMetadata(crosses_data_boundary=True)) == "high"


def test_high_risk_when_under_legal_hold_even_without_pii():
    assert classify_risk(DocumentMetadata(legal_hold=True)) == "high"


def test_high_risk_takes_priority_over_medium():
    assert classify_risk(DocumentMetadata(contains_pii=True, crosses_data_boundary=True)) == "high"
