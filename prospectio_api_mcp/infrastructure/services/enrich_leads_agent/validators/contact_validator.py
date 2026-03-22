import logging
import re
from urllib.parse import urlparse

from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.validation_result import ValidationResult
from domain.ports.contact_validator import ContactValidatorPort

logger = logging.getLogger(__name__)


class ContactValidator(ContactValidatorPort):
    """
    Implementation of contact validation using rule-based scoring.

    Scoring rules:
    - Email domain matches company domain: +40 points
    - Name found in original search results: +20 points
    - LinkedIn URL valid: +20 points
    - Job title matches search: +10 points
    - Has email: +10 points
    - Has phone: +5 points
    """

    # Scoring weights
    EMAIL_DOMAIN_MATCH_POINTS = 40
    NAME_IN_SEARCH_POINTS = 20
    LINKEDIN_VALID_POINTS = 20
    TITLE_MATCHES_POINTS = 10
    HAS_EMAIL_POINTS = 10
    HAS_PHONE_POINTS = 5

    def validate_contact(
        self,
        contact: Contact,
        company: Company,
        search_answer: str,
        searched_job_title: str,
    ) -> ValidationResult:
        """
        Validate an extracted contact and return a confidence score.

        Args:
            contact: The contact entity to validate.
            company: The company the contact is associated with.
            search_answer: The original search results text used for extraction.
            searched_job_title: The job title that was searched for.

        Returns:
            ValidationResult: The validation result with confidence score and details.
        """
        score = 0
        reasons: list[str] = []

        # Extract company domain for email validation
        company_domain = self._extract_company_domain(company)

        # Check email domain match
        email_domain_valid = self._validate_email_domain(
            contact.email, company_domain
        )
        if email_domain_valid:
            score += self.EMAIL_DOMAIN_MATCH_POINTS
            reasons.append(f"Email domain matches company domain (+{self.EMAIL_DOMAIN_MATCH_POINTS})")
        elif contact.email and company_domain:
            reasons.append("Email domain does not match company domain")

        # Check if name is in search results
        name_found = self._name_in_search_results(contact.name, search_answer)
        if name_found:
            score += self.NAME_IN_SEARCH_POINTS
            reasons.append(f"Name found in search results (+{self.NAME_IN_SEARCH_POINTS})")
        else:
            reasons.append("Name not found in original search results")

        # Check LinkedIn URL validity
        linkedin_valid = self._validate_linkedin_url(contact.profile_url)
        if linkedin_valid:
            score += self.LINKEDIN_VALID_POINTS
            reasons.append(f"Valid LinkedIn URL found (+{self.LINKEDIN_VALID_POINTS})")
        elif contact.profile_url:
            reasons.append("LinkedIn URL format is invalid")

        # Check title matches search
        title_matches = self._title_matches_search(contact.title, searched_job_title)
        if title_matches:
            score += self.TITLE_MATCHES_POINTS
            reasons.append(f"Job title matches search criteria (+{self.TITLE_MATCHES_POINTS})")
        else:
            reasons.append("Job title does not match search criteria")

        # Check if contact has email
        if contact.email and len(contact.email) > 0:
            score += self.HAS_EMAIL_POINTS
            reasons.append(f"Contact has email address (+{self.HAS_EMAIL_POINTS})")

        # Check if contact has phone
        if contact.phone and contact.phone.strip():
            score += self.HAS_PHONE_POINTS
            reasons.append(f"Contact has phone number (+{self.HAS_PHONE_POINTS})")

        logger.info(
            f"Validated contact '{contact.name}' with score {score}: "
            f"email_domain={email_domain_valid}, name_found={name_found}, "
            f"linkedin={linkedin_valid}, title_match={title_matches}"
        )

        return ValidationResult.from_score(
            confidence_score=score,
            validation_reasons=reasons,
            email_domain_valid=email_domain_valid,
            linkedin_valid=linkedin_valid,
            name_found_in_search=name_found,
            title_matches_search=title_matches,
        )

    def _extract_company_domain(self, company: Company) -> str | None:
        """
        Extract the domain from a company's website URL.

        Args:
            company: The company entity.

        Returns:
            str | None: The domain (e.g., 'example.com') or None if not available.
        """
        if not company.website:
            # Try to infer domain from company name
            if company.name:
                # Clean company name and create likely domain
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', company.name.lower())
                return clean_name
            return None

        try:
            parsed = urlparse(company.website)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix if present
            domain = re.sub(r'^www\.', '', domain)
            # Get the main domain (e.g., 'example.com' from 'subdomain.example.com')
            parts = domain.split('.')
            if len(parts) >= 2:
                return '.'.join(parts[-2:])
            return domain
        except Exception as e:
            logger.warning(f"Error extracting domain from {company.website}: {e}")
            return None

    def _validate_email_domain(
        self, emails: list[str] | None, company_domain: str | None
    ) -> bool:
        """
        Check if any email domain matches the company domain.

        Args:
            emails: List of email addresses.
            company_domain: The company domain to match against.

        Returns:
            bool: True if any email domain matches the company domain.
        """
        if not emails or not company_domain:
            return False

        company_domain_lower = company_domain.lower()

        for email in emails:
            if '@' not in email:
                continue

            email_domain = email.split('@')[-1].lower()

            # Direct match
            if email_domain == company_domain_lower:
                return True

            # Check if company domain is in email domain (for subdomains)
            if company_domain_lower in email_domain:
                return True

            # Check if email domain contains company name (minimum 3 chars to avoid false positives)
            company_name_part = company_domain_lower.split('.')[0]
            if company_name_part and len(company_name_part) >= 3 and company_name_part in email_domain:
                return True

        return False

    def _name_in_search_results(self, name: str | None, search_answer: str) -> bool:
        """
        Check if the contact's name appears in the original search results.

        Args:
            name: The contact's full name.
            search_answer: The original search results text.

        Returns:
            bool: True if the name is found in the search results.
        """
        if not name or not search_answer:
            return False

        name_lower = name.lower().strip()
        search_lower = search_answer.lower()

        # Check for full name match
        if name_lower in search_lower:
            return True

        # Check for first and last name separately
        name_parts = name_lower.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = name_parts[-1]
            # Both first and last name should be in the search results
            if first_name in search_lower and last_name in search_lower:
                return True

        return False

    def _validate_linkedin_url(self, profile_url: str | None) -> bool:
        """
        Validate that the profile URL is a valid LinkedIn profile URL.

        Args:
            profile_url: The profile URL to validate.

        Returns:
            bool: True if it's a valid LinkedIn profile URL.
        """
        if not profile_url or not profile_url.strip():
            return False

        # Handle comma-separated URLs (take the first one)
        url = profile_url.split(',')[0].strip()

        # LinkedIn URL patterns
        linkedin_patterns = [
            r'https?://(?:www\.)?linkedin\.com/in/[\w-]+/?',
            r'https?://(?:www\.)?linkedin\.com/pub/[\w-]+(?:/[\w-]+)*/?',
        ]

        for pattern in linkedin_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True

        return False

    def _title_matches_search(
        self, contact_title: str | None, searched_title: str
    ) -> bool:
        """
        Check if the contact's job title matches the searched job title.

        Uses fuzzy matching to account for variations (e.g., 'VP of Sales' matches 'Sales Manager').

        Args:
            contact_title: The contact's job title.
            searched_title: The job title that was searched for.

        Returns:
            bool: True if the titles are considered a match.
        """
        if not contact_title or not searched_title:
            return False

        contact_lower = contact_title.lower().strip()
        search_lower = searched_title.lower().strip()

        # Direct match or containment
        if search_lower in contact_lower or contact_lower in search_lower:
            return True

        # Extract key words from both titles and check for overlap
        # Common job title words to ignore
        stop_words = {
            'of', 'the', 'and', 'a', 'an', 'in', 'at', 'for', 'to',
            'senior', 'junior', 'lead', 'chief', 'head', 'associate',
            'assistant', 'executive', 'principal', 'staff', 'global',
            'regional', 'national', 'international', 'vice', 'deputy'
        }

        def extract_keywords(title: str) -> set[str]:
            words = re.findall(r'\b[a-z]+\b', title.lower())
            return {w for w in words if w not in stop_words and len(w) > 2}

        contact_keywords = extract_keywords(contact_title)
        search_keywords = extract_keywords(searched_title)

        # If any significant keywords match, consider it a match
        if contact_keywords & search_keywords:
            return True

        return False
