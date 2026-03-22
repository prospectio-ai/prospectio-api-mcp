"""
Unit tests for ContactValidator service.

Tests the rule-based contact validation scoring system that validates
extracted contacts against company information and search results.

Scoring rules:
- Email domain matches company domain: +40 points
- Name found in original search results: +20 points
- LinkedIn URL valid: +20 points
- Job title matches search: +10 points
- Has email: +10 points
- Has phone: +5 points

Thresholds:
- VERIFIED (70-100): High confidence
- LIKELY_VALID (40-69): Medium confidence
- NEEDS_REVIEW (0-39): Low confidence
"""

import pytest

from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.validation_result import ValidationStatus
from infrastructure.services.enrich_leads_agent.validators.contact_validator import (
    ContactValidator,
)


class TestContactValidatorFixtures:
    """Fixtures for ContactValidator tests."""

    @pytest.fixture
    def validator(self) -> ContactValidator:
        """Create a ContactValidator instance for testing."""
        return ContactValidator()

    @pytest.fixture
    def sample_company(self) -> Company:
        """Company with website for domain extraction."""
        return Company(
            id="company-123",
            name="Acme Corp",
            website="https://www.acme.com",
            industry="Technology",
            location="Paris, France",
        )

    @pytest.fixture
    def sample_company_no_website(self) -> Company:
        """Company without website (domain derived from name)."""
        return Company(
            id="company-456",
            name="TechStartup",
            website=None,
            industry="Software",
        )

    @pytest.fixture
    def high_confidence_contact(self) -> Contact:
        """Contact likely to score high (verified)."""
        return Contact(
            id="contact-001",
            name="John Doe",
            email=["john.doe@acme.com"],
            title="CTO",  # Matches searched_job_title="CTO" exactly
            phone="+33 1 23 45 67 89",
            profile_url="https://www.linkedin.com/in/john-doe",
        )

    @pytest.fixture
    def medium_confidence_contact(self) -> Contact:
        """Contact likely to score medium (likely valid)."""
        return Contact(
            id="contact-002",
            name="Jane Smith",
            email=["jane.smith@acme.com"],
            title="Project Manager",
            phone=None,
            profile_url=None,
        )

    @pytest.fixture
    def low_confidence_contact(self) -> Contact:
        """Contact likely to score low (needs review)."""
        return Contact(
            id="contact-003",
            name="Unknown Person",
            email=["unknown@gmail.com"],
            title="Unknown Title",
            phone=None,
            profile_url=None,
        )

    @pytest.fixture
    def search_answer_with_name(self) -> str:
        """Search text containing contact name."""
        return """
        After searching for CTO at Acme Corp, I found the following contact:
        John Doe is the CTO at Acme Corp.
        He has been leading the technology department for 5 years.
        Contact information: john.doe@acme.com
        LinkedIn: https://linkedin.com/in/john-doe
        """

    @pytest.fixture
    def search_answer_without_name(self) -> str:
        """Search text not containing contact name."""
        return """
        Acme Corp is a technology company based in Paris.
        They specialize in cloud computing solutions.
        The company has about 500 employees.
        """


class TestContactValidatorHighConfidence(TestContactValidatorFixtures):
    """Tests for high confidence (verified) validation results."""

    def test_returns_verified_status_with_all_criteria_met(
        self,
        validator: ContactValidator,
        sample_company: Company,
        high_confidence_contact: Contact,
        search_answer_with_name: str,
    ):
        """Contact with all validation criteria met should score >= 70 and be verified."""
        result = validator.validate_contact(
            contact=high_confidence_contact,
            company=sample_company,
            search_answer=search_answer_with_name,
            searched_job_title="CTO",
        )

        assert result.confidence_score >= 70
        assert result.validation_status == ValidationStatus.VERIFIED
        assert result.email_domain_valid is True
        assert result.linkedin_valid is True
        assert result.name_found_in_search is True
        assert result.title_matches_search is True

    def test_maximum_score_calculation(
        self,
        validator: ContactValidator,
        sample_company: Company,
        high_confidence_contact: Contact,
        search_answer_with_name: str,
    ):
        """Contact meeting all criteria should score 105 (capped at 100)."""
        # Maximum possible: 40 + 20 + 20 + 10 + 10 + 5 = 105
        result = validator.validate_contact(
            contact=high_confidence_contact,
            company=sample_company,
            search_answer=search_answer_with_name,
            searched_job_title="CTO",
        )

        # Score is capped at 100
        assert result.confidence_score == 100


class TestContactValidatorMediumConfidence(TestContactValidatorFixtures):
    """Tests for medium confidence (likely valid) validation results."""

    def test_returns_likely_valid_with_email_domain_match_only(
        self,
        validator: ContactValidator,
        sample_company: Company,
        search_answer_without_name: str,
    ):
        """Contact with matching email domain but no LinkedIn should be likely valid."""
        contact = Contact(
            name="New Hire",
            email=["new.hire@acme.com"],
            title="Junior Developer",
            phone=None,
            profile_url=None,
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer=search_answer_without_name,
            searched_job_title="Senior Engineer",
        )

        # Score: 40 (email domain) + 10 (has email) = 50
        assert 40 <= result.confidence_score < 70
        assert result.validation_status == ValidationStatus.LIKELY_VALID
        assert result.email_domain_valid is True
        assert result.linkedin_valid is False

    def test_returns_likely_valid_with_linkedin_and_name_match(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Contact with valid LinkedIn and name in search but generic email."""
        contact = Contact(
            name="Alice Martin",
            email=["alice.martin@gmail.com"],
            title="Director",
            phone=None,
            profile_url="https://www.linkedin.com/in/alice-martin",
        )

        search_answer = "Alice Martin is a Director at Acme Corp."

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer=search_answer,
            searched_job_title="Director",
        )

        # Score: 20 (name) + 20 (LinkedIn) + 10 (title) + 10 (email) = 60
        assert 40 <= result.confidence_score < 70
        assert result.validation_status == ValidationStatus.LIKELY_VALID


class TestContactValidatorLowConfidence(TestContactValidatorFixtures):
    """Tests for low confidence (needs review) validation results."""

    def test_returns_needs_review_with_generic_email_no_linkedin(
        self,
        validator: ContactValidator,
        sample_company: Company,
        low_confidence_contact: Contact,
        search_answer_without_name: str,
    ):
        """Contact with generic email (gmail) and no LinkedIn should need review."""
        result = validator.validate_contact(
            contact=low_confidence_contact,
            company=sample_company,
            search_answer=search_answer_without_name,
            searched_job_title="CTO",
        )

        assert result.confidence_score < 40
        assert result.validation_status == ValidationStatus.NEEDS_REVIEW
        assert result.email_domain_valid is False
        assert result.linkedin_valid is False

    def test_minimal_score_with_only_email_present(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Contact with only generic email should have minimal score."""
        contact = Contact(
            name="Nobody",
            email=["nobody@hotmail.com"],
            title=None,
            phone=None,
            profile_url=None,
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="",
            searched_job_title="CEO",
        )

        # Score: 10 (has email) only
        assert result.confidence_score == 10
        assert result.validation_status == ValidationStatus.NEEDS_REVIEW


class TestExtractCompanyDomain(TestContactValidatorFixtures):
    """Tests for _extract_company_domain method."""

    def test_extracts_domain_from_full_url(self, validator: ContactValidator):
        """Should extract domain from full website URL."""
        company = Company(name="Test", website="https://www.example.com/about")

        domain = validator._extract_company_domain(company)

        assert domain == "example.com"

    def test_extracts_domain_from_url_without_www(self, validator: ContactValidator):
        """Should extract domain from URL without www prefix."""
        company = Company(name="Test", website="https://acme.com/products")

        domain = validator._extract_company_domain(company)

        assert domain == "acme.com"

    def test_handles_subdomain(self, validator: ContactValidator):
        """Should extract main domain from subdomain URL."""
        company = Company(name="Test", website="https://shop.example.com")

        domain = validator._extract_company_domain(company)

        assert domain == "example.com"

    def test_derives_domain_from_company_name_when_no_website(
        self, validator: ContactValidator
    ):
        """Should derive domain from company name when website is missing."""
        company = Company(name="Acme Corp", website=None)

        domain = validator._extract_company_domain(company)

        assert domain == "acmecorp"

    def test_returns_none_when_no_website_and_no_name(
        self, validator: ContactValidator
    ):
        """Should return None when neither website nor name is available."""
        company = Company(name=None, website=None)

        domain = validator._extract_company_domain(company)

        assert domain is None

    def test_cleans_special_characters_from_company_name(
        self, validator: ContactValidator
    ):
        """Should remove special characters when deriving domain from name."""
        company = Company(name="Tech & Solutions S.A.", website=None)

        domain = validator._extract_company_domain(company)

        assert domain == "techsolutionssa"


class TestValidateEmailDomain(TestContactValidatorFixtures):
    """Tests for _validate_email_domain method."""

    def test_returns_true_for_exact_domain_match(self, validator: ContactValidator):
        """Should return True when email domain exactly matches company domain."""
        result = validator._validate_email_domain(
            emails=["john@acme.com"], company_domain="acme.com"
        )

        assert result is True

    def test_returns_true_for_subdomain_match(self, validator: ContactValidator):
        """Should return True when email domain is a subdomain of company domain."""
        result = validator._validate_email_domain(
            emails=["john@mail.acme.com"], company_domain="acme.com"
        )

        assert result is True

    def test_returns_true_when_company_name_in_email_domain(
        self, validator: ContactValidator
    ):
        """Should return True when company name appears in email domain."""
        result = validator._validate_email_domain(
            emails=["john@acme-corp.com"], company_domain="acme.com"
        )

        assert result is True

    def test_returns_false_for_generic_email(self, validator: ContactValidator):
        """Should return False for generic email providers like gmail."""
        result = validator._validate_email_domain(
            emails=["john@gmail.com"], company_domain="acme.com"
        )

        assert result is False

    def test_returns_false_when_no_emails(self, validator: ContactValidator):
        """Should return False when email list is None or empty."""
        assert validator._validate_email_domain(None, "acme.com") is False
        assert validator._validate_email_domain([], "acme.com") is False

    def test_returns_false_when_no_company_domain(self, validator: ContactValidator):
        """Should return False when company domain is None."""
        result = validator._validate_email_domain(
            emails=["john@acme.com"], company_domain=None
        )

        assert result is False

    def test_checks_multiple_emails(self, validator: ContactValidator):
        """Should return True if any email matches company domain."""
        result = validator._validate_email_domain(
            emails=["personal@gmail.com", "work@acme.com"],
            company_domain="acme.com",
        )

        assert result is True

    def test_handles_email_without_at_symbol(self, validator: ContactValidator):
        """Should skip malformed emails without @ symbol."""
        result = validator._validate_email_domain(
            emails=["not-an-email", "valid@acme.com"],
            company_domain="acme.com",
        )

        assert result is True

    def test_case_insensitive_matching(self, validator: ContactValidator):
        """Should match domains case-insensitively."""
        result = validator._validate_email_domain(
            emails=["John@ACME.COM"], company_domain="acme.com"
        )

        assert result is True


class TestNameInSearchResults(TestContactValidatorFixtures):
    """Tests for _name_in_search_results method."""

    def test_returns_true_for_full_name_match(self, validator: ContactValidator):
        """Should return True when full name is found in search results."""
        result = validator._name_in_search_results(
            name="John Doe",
            search_answer="John Doe is the CEO of Acme Corp.",
        )

        assert result is True

    def test_returns_true_for_first_and_last_name_match(
        self, validator: ContactValidator
    ):
        """Should return True when first and last name are both in search."""
        result = validator._name_in_search_results(
            name="John Doe",
            search_answer="I found John who works at Acme. His last name is Doe.",
        )

        assert result is True

    def test_returns_false_when_only_first_name_matches(
        self, validator: ContactValidator
    ):
        """Should return False when only first name is found."""
        result = validator._name_in_search_results(
            name="John Doe",
            search_answer="John Smith is the CEO of Acme Corp.",
        )

        assert result is False

    def test_returns_false_when_name_not_in_search(self, validator: ContactValidator):
        """Should return False when name is not in search results."""
        result = validator._name_in_search_results(
            name="Alice Martin",
            search_answer="John Doe is the CEO of Acme Corp.",
        )

        assert result is False

    def test_returns_false_for_empty_name(self, validator: ContactValidator):
        """Should return False when name is None or empty."""
        assert validator._name_in_search_results(None, "Some search text") is False
        assert validator._name_in_search_results("", "Some search text") is False

    def test_returns_false_for_empty_search_answer(self, validator: ContactValidator):
        """Should return False when search answer is empty."""
        assert validator._name_in_search_results("John Doe", "") is False
        assert validator._name_in_search_results("John Doe", None) is False

    def test_case_insensitive_name_matching(self, validator: ContactValidator):
        """Should match names case-insensitively."""
        result = validator._name_in_search_results(
            name="JOHN DOE",
            search_answer="john doe is the ceo",
        )

        assert result is True


class TestValidateLinkedInUrl(TestContactValidatorFixtures):
    """Tests for _validate_linkedin_url method."""

    def test_returns_true_for_valid_linkedin_in_url(self, validator: ContactValidator):
        """Should return True for standard LinkedIn /in/ profile URL."""
        result = validator._validate_linkedin_url(
            "https://www.linkedin.com/in/john-doe"
        )

        assert result is True

    def test_returns_true_for_linkedin_url_without_www(
        self, validator: ContactValidator
    ):
        """Should return True for LinkedIn URL without www."""
        result = validator._validate_linkedin_url("https://linkedin.com/in/john-doe")

        assert result is True

    def test_returns_true_for_linkedin_pub_url(self, validator: ContactValidator):
        """Should return True for LinkedIn /pub/ profile URL."""
        result = validator._validate_linkedin_url(
            "https://www.linkedin.com/pub/john-doe/123/abc/xyz"
        )

        assert result is True

    def test_returns_true_for_http_url(self, validator: ContactValidator):
        """Should return True for HTTP (non-HTTPS) LinkedIn URL."""
        result = validator._validate_linkedin_url("http://www.linkedin.com/in/john-doe")

        assert result is True

    def test_returns_false_for_invalid_linkedin_url(self, validator: ContactValidator):
        """Should return False for non-LinkedIn URLs."""
        assert validator._validate_linkedin_url("https://twitter.com/john-doe") is False
        assert (
            validator._validate_linkedin_url("https://linkedin.com/company/acme")
            is False
        )
        assert validator._validate_linkedin_url("not-a-url") is False

    def test_returns_false_for_empty_url(self, validator: ContactValidator):
        """Should return False for None or empty URL."""
        assert validator._validate_linkedin_url(None) is False
        assert validator._validate_linkedin_url("") is False
        assert validator._validate_linkedin_url("   ") is False

    def test_handles_comma_separated_urls(self, validator: ContactValidator):
        """Should validate first URL when comma-separated URLs are provided."""
        result = validator._validate_linkedin_url(
            "https://linkedin.com/in/john-doe, https://linkedin.com/in/other"
        )

        assert result is True

    def test_handles_trailing_slash(self, validator: ContactValidator):
        """Should accept LinkedIn URLs with trailing slash."""
        result = validator._validate_linkedin_url(
            "https://www.linkedin.com/in/john-doe/"
        )

        assert result is True


class TestTitleMatchesSearch(TestContactValidatorFixtures):
    """Tests for _title_matches_search method."""

    def test_returns_true_for_exact_match(self, validator: ContactValidator):
        """Should return True for exact title match."""
        result = validator._title_matches_search(
            contact_title="CTO",
            searched_title="CTO",
        )

        assert result is True

    def test_returns_true_when_search_title_in_contact_title(
        self, validator: ContactValidator
    ):
        """Should return True when searched title is contained in contact title."""
        result = validator._title_matches_search(
            contact_title="Chief Technology Officer",
            searched_title="Technology Officer",
        )

        assert result is True

    def test_returns_true_when_contact_title_in_search_title(
        self, validator: ContactValidator
    ):
        """Should return True when contact title is contained in searched title."""
        result = validator._title_matches_search(
            contact_title="Sales Manager",
            searched_title="Senior Sales Manager EMEA",
        )

        assert result is True

    def test_returns_true_for_keyword_match(self, validator: ContactValidator):
        """Should return True when significant keywords match."""
        result = validator._title_matches_search(
            contact_title="VP of Sales",
            searched_title="Sales Director",
        )

        assert result is True

    def test_ignores_seniority_words(self, validator: ContactValidator):
        """Should match titles ignoring seniority prefixes."""
        result = validator._title_matches_search(
            contact_title="Senior Software Engineer",
            searched_title="Junior Developer",
        )

        # "software" and "developer" are different keywords
        assert result is False

    def test_returns_false_for_unrelated_titles(self, validator: ContactValidator):
        """Should return False for completely unrelated titles."""
        result = validator._title_matches_search(
            contact_title="Marketing Director",
            searched_title="Software Engineer",
        )

        assert result is False

    def test_returns_false_for_empty_titles(self, validator: ContactValidator):
        """Should return False when either title is None or empty."""
        assert validator._title_matches_search(None, "CTO") is False
        assert validator._title_matches_search("CTO", None) is False
        assert validator._title_matches_search("", "CTO") is False
        assert validator._title_matches_search("CTO", "") is False

    def test_case_insensitive_matching(self, validator: ContactValidator):
        """Should match titles case-insensitively."""
        result = validator._title_matches_search(
            contact_title="CHIEF EXECUTIVE OFFICER",
            searched_title="chief executive officer",
        )

        assert result is True


class TestContactValidatorEdgeCases(TestContactValidatorFixtures):
    """Tests for edge cases in contact validation."""

    def test_contact_without_email(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Contact without email should not get email-related points."""
        contact = Contact(
            name="John Doe",
            email=None,
            title="CTO",
            phone="+33 1 23 45 67 89",
            profile_url="https://linkedin.com/in/john-doe",
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="John Doe is the CTO",
            searched_job_title="CTO",
        )

        assert result.email_domain_valid is False
        # Score: 20 (name) + 20 (LinkedIn) + 10 (title) + 5 (phone) = 55
        assert result.confidence_score == 55
        assert result.validation_status == ValidationStatus.LIKELY_VALID

    def test_contact_without_linkedin(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Contact without LinkedIn should not get LinkedIn points."""
        contact = Contact(
            name="Jane Smith",
            email=["jane@acme.com"],
            title="CTO",
            phone=None,
            profile_url=None,
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="Jane Smith is the CTO",
            searched_job_title="CTO",
        )

        assert result.linkedin_valid is False
        # Score: 40 (email) + 20 (name) + 10 (title) + 10 (has email) = 80
        assert result.confidence_score == 80
        assert result.validation_status == ValidationStatus.VERIFIED

    def test_company_without_website_derives_domain_from_name(
        self,
        validator: ContactValidator,
        sample_company_no_website: Company,
    ):
        """Should derive domain from company name when website is missing."""
        contact = Contact(
            name="Bob Builder",
            email=["bob@techstartup.com"],
            title="Developer",
            phone=None,
            profile_url=None,
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company_no_website,
            search_answer="Bob Builder works here",
            searched_job_title="Developer",
        )

        # "techstartup" from email should match derived domain "techstartup"
        assert result.email_domain_valid is True

    def test_empty_search_results(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Contact with empty search results should not get name-in-search points."""
        contact = Contact(
            name="John Doe",
            email=["john@acme.com"],
            title="CTO",
            phone=None,
            profile_url="https://linkedin.com/in/john-doe",
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="",
            searched_job_title="CTO",
        )

        assert result.name_found_in_search is False
        # Score: 40 (email) + 20 (LinkedIn) + 10 (title) + 10 (has email) = 80
        assert result.confidence_score == 80

    def test_validation_reasons_are_populated(
        self,
        validator: ContactValidator,
        sample_company: Company,
        high_confidence_contact: Contact,
        search_answer_with_name: str,
    ):
        """Validation reasons should explain the score breakdown."""
        result = validator.validate_contact(
            contact=high_confidence_contact,
            company=sample_company,
            search_answer=search_answer_with_name,
            searched_job_title="CTO",
        )

        assert len(result.validation_reasons) > 0
        # Check for expected reason messages
        reasons_text = " ".join(result.validation_reasons)
        assert "Email domain matches" in reasons_text
        assert "Name found" in reasons_text
        assert "LinkedIn URL" in reasons_text
        assert "Job title matches" in reasons_text

    def test_invalid_linkedin_url_adds_negative_reason(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Invalid LinkedIn URL should add explanation to reasons."""
        contact = Contact(
            name="Test User",
            email=["test@acme.com"],
            title="Developer",
            phone=None,
            profile_url="https://twitter.com/testuser",  # Not LinkedIn
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="",
            searched_job_title="Developer",
        )

        assert result.linkedin_valid is False
        assert any("invalid" in r.lower() for r in result.validation_reasons)

    def test_email_domain_mismatch_adds_negative_reason(
        self,
        validator: ContactValidator,
        sample_company: Company,
    ):
        """Mismatched email domain should add explanation to reasons."""
        contact = Contact(
            name="Test User",
            email=["test@gmail.com"],
            title="Developer",
            phone=None,
            profile_url=None,
        )

        result = validator.validate_contact(
            contact=contact,
            company=sample_company,
            search_answer="",
            searched_job_title="Developer",
        )

        assert result.email_domain_valid is False
        assert any(
            "does not match" in r.lower() for r in result.validation_reasons
        )


class TestContactValidatorScoreComponents(TestContactValidatorFixtures):
    """Tests verifying individual score components."""

    def test_email_domain_match_adds_40_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Email domain matching company domain should add 40 points."""
        contact_with_match = Contact(
            name="Nobody",
            email=["test@acme.com"],
            title=None,
            phone=None,
            profile_url=None,
        )
        contact_without_match = Contact(
            name="Nobody",
            email=["test@gmail.com"],
            title=None,
            phone=None,
            profile_url=None,
        )

        result_with = validator.validate_contact(
            contact_with_match, sample_company, "", ""
        )
        result_without = validator.validate_contact(
            contact_without_match, sample_company, "", ""
        )

        assert result_with.confidence_score - result_without.confidence_score == 40

    def test_name_in_search_adds_20_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Name found in search should add 20 points."""
        contact = Contact(
            name="John Doe",
            email=None,
            title=None,
            phone=None,
            profile_url=None,
        )

        result_with_name = validator.validate_contact(
            contact, sample_company, "John Doe is here", ""
        )
        result_without_name = validator.validate_contact(
            contact, sample_company, "Nobody is here", ""
        )

        assert result_with_name.confidence_score - result_without_name.confidence_score == 20

    def test_linkedin_valid_adds_20_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Valid LinkedIn URL should add 20 points."""
        contact_with_linkedin = Contact(
            name="Test",
            email=None,
            title=None,
            phone=None,
            profile_url="https://linkedin.com/in/test",
        )
        contact_without_linkedin = Contact(
            name="Test",
            email=None,
            title=None,
            phone=None,
            profile_url=None,
        )

        result_with = validator.validate_contact(
            contact_with_linkedin, sample_company, "", ""
        )
        result_without = validator.validate_contact(
            contact_without_linkedin, sample_company, "", ""
        )

        assert result_with.confidence_score - result_without.confidence_score == 20

    def test_title_match_adds_10_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Matching title should add 10 points."""
        contact = Contact(
            name="Test",
            email=None,
            title="CTO",
            phone=None,
            profile_url=None,
        )

        result_with_match = validator.validate_contact(
            contact, sample_company, "", "CTO"
        )
        result_without_match = validator.validate_contact(
            contact, sample_company, "", "HR Manager"
        )

        assert result_with_match.confidence_score - result_without_match.confidence_score == 10

    def test_has_email_adds_10_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Having an email should add 10 points."""
        contact_with_email = Contact(
            name="Test",
            email=["test@gmail.com"],
            title=None,
            phone=None,
            profile_url=None,
        )
        contact_without_email = Contact(
            name="Test",
            email=None,
            title=None,
            phone=None,
            profile_url=None,
        )

        result_with = validator.validate_contact(
            contact_with_email, sample_company, "", ""
        )
        result_without = validator.validate_contact(
            contact_without_email, sample_company, "", ""
        )

        assert result_with.confidence_score - result_without.confidence_score == 10

    def test_has_phone_adds_5_points(
        self, validator: ContactValidator, sample_company: Company
    ):
        """Having a phone number should add 5 points."""
        contact_with_phone = Contact(
            name="Test",
            email=None,
            title=None,
            phone="+33 1 23 45 67 89",
            profile_url=None,
        )
        contact_without_phone = Contact(
            name="Test",
            email=None,
            title=None,
            phone=None,
            profile_url=None,
        )

        result_with = validator.validate_contact(
            contact_with_phone, sample_company, "", ""
        )
        result_without = validator.validate_contact(
            contact_without_phone, sample_company, "", ""
        )

        assert result_with.confidence_score - result_without.confidence_score == 5
