from document_intelligence.golden_set import GoldenCase, check_for_regressions, run_golden_set

CASES = [
    GoldenCase(name="termination_notice", document="60 days written notice.", question="q1", expected_answer_contains="60 days"),
    GoldenCase(name="payment_terms", document="pay within 30 days.", question="q2", expected_answer_contains="30 days"),
]


def test_run_golden_set_reports_pass_and_fail_per_case():
    def good_answer_fn(question, document):
        return {"answer": "60 days" if "60" in document else "30 days"}

    results = run_golden_set(CASES, good_answer_fn)
    assert all(r.passed for r in results)


def test_run_golden_set_catches_a_wrong_answer():
    def broken_answer_fn(question, document):
        return {"answer": "wrong answer entirely"}

    results = run_golden_set(CASES, broken_answer_fn)
    assert all(not r.passed for r in results)


def test_check_for_regressions_finds_only_newly_broken_cases():
    before = [
        type("R", (), {"name": "a", "passed": True})(),
        type("R", (), {"name": "b", "passed": True})(),
    ]
    after = [
        type("R", (), {"name": "a", "passed": True})(),
        type("R", (), {"name": "b", "passed": False})(),  # this one regressed
    ]
    assert check_for_regressions(before, after) == ["b"]


def test_check_for_regressions_reports_nothing_when_stable():
    before = [type("R", (), {"name": "a", "passed": True})()]
    after = [type("R", (), {"name": "a", "passed": True})()]
    assert check_for_regressions(before, after) == []
