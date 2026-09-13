from sre_agent.durable_task import Step, TaskStore, resume


def test_resume_runs_every_step_on_a_fresh_task():
    store = TaskStore()
    calls = []
    plan = [
        Step("drain", lambda: calls.append("drain")),
        Step("restart", lambda: calls.append("restart")),
    ]
    ran = resume(store, "task-1", plan)
    assert ran == ["drain", "restart"]
    assert calls == ["drain", "restart"]


def test_resume_skips_already_completed_steps():
    store = TaskStore()
    calls = []
    plan = [
        Step("drain", lambda: calls.append("drain")),
        Step("restart", lambda: calls.append("restart")),
    ]
    resume(store, "task-1", plan)  # first pass completes both

    calls.clear()
    ran_again = resume(store, "task-1", plan)  # simulates a fresh process resuming
    assert ran_again == []
    assert calls == []  # neither step re-ran


def test_resume_continues_from_the_first_incomplete_step():
    store = TaskStore()
    store.set_status("task-1", "drain", "completed")  # pretend drain already ran
    calls = []
    plan = [
        Step("drain", lambda: calls.append("drain")),
        Step("restart", lambda: calls.append("restart")),
    ]
    ran = resume(store, "task-1", plan)
    assert ran == ["restart"]
    assert calls == ["restart"]
