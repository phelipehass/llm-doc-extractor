from app.schema import ContractFields
from evaluation.run import score


def test_score_is_lenient_on_formatting_but_strict_on_values():
    got = ContractFields(
        parties=["ACME, Inc., a Delaware corporation", "Globex LLC"],
        effective_date="2019-03-01",
        governing_law="the State of Delaware",
        termination_notice_days=60,
    )
    expected = {
        "parties": ["Acme Inc", "Globex LLC"],
        "effective_date": "2019-03-01",
        "governing_law": "Delaware",
        "termination_notice_days": 30,
    }

    assert score(expected, got) == {
        "parties": True,
        "effective_date": True,
        "governing_law": True,
        "termination_notice_days": False,
    }


def test_only_labeled_fields_are_scored():
    assert score({"governing_law": None}, ContractFields()) == {"governing_law": True}


def test_cuad_label_parsing():
    from evaluation.make_cuad_cases import parse_date, parse_parties

    assert parse_parties(
        'PSiTech Corporation ("Licensor"); Empirical Ventures, Inc ("Licensee")'
    ) == [
        "PSiTech Corporation",
        "Empirical Ventures, Inc",
    ]
    assert str(parse_date("2/10/14")) == "2014-02-10"
    assert str(parse_date("7/1/2019")) == "2019-07-01"
    assert parse_date("[]") is None
