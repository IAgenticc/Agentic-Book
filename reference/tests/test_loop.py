from sre_agent.loop import bounded_loop
from sre_agent.models import FakeModel


def test_loop_stops_when_is_done_true():
    model = FakeModel(responder=lambda p: "final answer")
    result = bounded_loop(model, "start", is_done=lambda r: "final" in r, max_steps=6)
    assert result.status == "done"
    assert result.steps == 1


def test_loop_stops_at_max_steps_if_never_done():
    model = FakeModel(responder=lambda p: "still thinking")
    result = bounded_loop(model, "start", is_done=lambda r: False, max_steps=4)
    assert result.status == "max_steps_reached"
    assert result.steps == 4
    assert model.calls == 4  # never exceeds the cap, no matter what the model says
