import pytest

from app.services.apply import auto_apply, build_application_pack, listing_contact_email


def test_build_application_pack_uses_cv_summary_not_invented_experience():
    job = {"title": "Solution Architect - Azure Cloud", "company": "Sanderson"}
    pack = build_application_pack(
        job,
        {
            "roles": ["Enterprise Architect", "Solutions Architect"],
            "summary": "Enterprise Architecture Leader with Azure and TOGAF.",
        },
    )
    assert "Solution Architect - Azure Cloud" in pack["cover_letter"]
    assert "Azure" in pack["cover_letter"]
    assert "Kubernetes cluster operator" not in pack["cover_letter"]


def test_listing_contact_email_extracts_real_address():
    job = {"description": "Apply to jane.recruiter@sanderson.com quoting ref 12."}
    assert listing_contact_email(job) == "jane.recruiter@sanderson.com"
    assert listing_contact_email({"description": "No contact listed"}) is None


@pytest.mark.asyncio
async def test_auto_apply_sends_via_unipile_when_listing_has_email(monkeypatch):
    async def fake_email(settings, **kwargs):
        assert kwargs["to_email"] == "jane.recruiter@sanderson.com"
        return True

    monkeypatch.setattr("app.services.unipile.send_unipile_email", fake_email)
    result = await auto_apply(
        {
            "title": "Solutions Architect",
            "description": "Apply to jane.recruiter@sanderson.com",
        },
        {"cover_letter": "Dear Hiring Manager"},
        {"raw_text": "Enterprise Architect with Azure."},
        type(
            "S",
            (),
            {
                "unipile_dsn": "https://api1.unipile.com:13465",
                "unipile_api_key": "key",
                "unipile_account_id": "acc",
            },
        )(),
    )
    assert result["submitted"] is True
    assert result["emailed"] is True
    assert result["channel"] == "unipile_email"


@pytest.mark.asyncio
async def test_auto_apply_does_not_fake_submit_without_smtp():
    result = await auto_apply(
        {
            "title": "Solutions Architect",
            "source_url": "https://example.com/job",
            "description": "No email here",
        },
        {"cover_letter": "Dear Hiring Manager"},
        {"raw_text": "Enterprise Architect with Azure."},
        type("S", (), {})(),
    )
    assert result["submitted"] is False
    assert result["emailed"] is False
    assert result["channel"] == "apply_blocked"
