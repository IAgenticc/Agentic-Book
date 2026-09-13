from sre_agent.models import FakeModel, ModelUnavailable, call_with_fallback


def test_call_with_fallback_uses_primary_when_healthy():
    primary = FakeModel(responder=lambda p: "primary answer")
    fallback = FakeModel(responder=lambda p: "fallback answer")
    result = call_with_fallback("q", primary, fallback, degraded=lambda p: {"text": "degraded"})
    assert result["text"] == "primary answer"
    assert result["source"] == "model"


def test_call_with_fallback_falls_through_to_fallback_on_primary_failure():
    primary = FakeModel(fail=True)
    fallback = FakeModel(responder=lambda p: "fallback answer")
    result = call_with_fallback("q", primary, fallback, degraded=lambda p: {"text": "degraded"})
    assert result["text"] == "fallback answer"


def test_call_with_fallback_reaches_degraded_mode_when_both_down():
    primary = FakeModel(fail=True)
    fallback = FakeModel(fail=True)
    result = call_with_fallback("q", primary, fallback, degraded=lambda p: {"text": "degraded", "source": "degraded"})
    assert result["source"] == "degraded"


def test_fake_model_raises_model_unavailable_when_configured_to_fail():
    model = FakeModel(fail=True)
    try:
        model.generate("x")
        assert False, "expected ModelUnavailable"
    except ModelUnavailable:
        pass
