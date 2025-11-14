from app.services.external_context.user.personal_information import PersonalInformationService


def test_profile_all_none_returns_empty_string():
    svc = PersonalInformationService()
    data = {"preferred_name": None, "pronoun_id": None, "birth_date": None, "location": None}
    assert svc._format_profile(data) == ""


def test_profile_preferred_name_only():
    svc = PersonalInformationService()
    data = {"preferred_name": "Gonza", "pronoun_id": None, "birth_date": None, "location": None}
    assert svc._format_profile(data) == "Their preferred name is Gonza."


def test_profile_pronoun_mapping_they_them():
    svc = PersonalInformationService()
    data = {"preferred_name": None, "pronoun_id": "they_them", "birth_date": None, "location": None}
    assert svc._format_profile(data) == "They use they/them pronouns."


def test_profile_birth_and_location_formatting():
    svc = PersonalInformationService()
    data = {"preferred_name": None, "pronoun_id": None, "birth_date": "1990-05-10", "location": "Buenos Aires"}
    assert svc._format_profile(data) == "The user was born on May 10, 1990 in Buenos Aires."


def test_profile_all_fields_combined():
    svc = PersonalInformationService()
    data = {
        "preferred_name": "Gonza",
        "pronoun_id": "they_them",
        "birth_date": "1990-05-10",
        "location": "Buenos Aires",
    }
    result = svc._format_profile(data)
    assert "The user was born on May 10, 1990 in Buenos Aires." in result
    assert "Their preferred name is Gonza." in result
    assert "They use they/them pronouns." in result


def test_vera_approach_ignores_none_interaction_style():
    svc = PersonalInformationService()
    data = {"interaction_style": None, "topics_to_avoid": None}
    assert svc._format_vera_approach(data) == ""


def test_health_insurance_ignores_none_coverage_keeps_payer():
    svc = PersonalInformationService()
    data = {"coverage_description": None, "pays_for_self": False}
    assert svc._format_health_insurance(data) == "Regarding health insurance: it's covered by someone else."


def test_learning_topics_omits_when_empty():
    svc = PersonalInformationService()
    data = {"topics": []}
    assert svc._format_learning_topics(data) == ""


def test_financial_goals_omits_when_empty():
    svc = PersonalInformationService()
    data = {"financial_goals": []}
    assert svc._format_financial_goals(data) == ""
