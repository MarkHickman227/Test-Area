from app.services.agency import detect_agency


def test_detects_agency_by_company_name():
    assert detect_agency(company="XYZ Recruitment Ltd") is True
    assert detect_agency(company="ABC Staffing Solutions") is True
    assert detect_agency(company="Tech Talent Acquisition Partners") is True


def test_detects_agency_by_description():
    assert detect_agency(description="We are recruiting on behalf of our client, a major bank") is True
    assert detect_agency(description="Acting for a leading technology company") is True


def test_detects_agency_by_email_domain():
    assert detect_agency(contact_email="john@xyzrecruitment.co.uk") is True
    assert detect_agency(contact_email="jobs@talentsearch.com") is True


def test_returns_false_for_direct_employer():
    assert detect_agency(company="Google", description="We are hiring an engineer") is False
    assert detect_agency(company="Barclays", contact_email="hr@barclays.com") is False


def test_returns_false_for_empty_inputs():
    assert detect_agency() is False
    assert detect_agency(company="", description="", contact_email="") is False
