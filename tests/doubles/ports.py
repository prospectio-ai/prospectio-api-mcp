"""Fake port implementations for testing."""

from typing import Optional

from domain.entities.company import Company
from domain.entities.contact import Contact
from domain.entities.profile import Profile
from domain.entities.prospect_message import ProspectMessage
from domain.ports.generate_message import GenerateMessagePort


class FakeGenerateMessagePort(GenerateMessagePort):
    """Fake implementation of GenerateMessagePort for testing."""

    def __init__(self):
        self._messages: dict[str, ProspectMessage] = {}
        self._should_fail_for: set[str] = set()
        self._default_message: Optional[ProspectMessage] = None
        self._call_count: int = 0

    async def get_message(
        self, profile: Profile, contact: Contact, company: Company
    ) -> ProspectMessage:
        """
        Generate a fake prospect message.

        Returns pre-configured message if available, otherwise generates a default one.
        Raises an exception if contact_id is in the failure set.
        """
        self._call_count += 1

        contact_id = contact.id or ""

        # Simulate failure for specific contacts
        if contact_id in self._should_fail_for:
            raise Exception(f"Simulated failure for contact {contact_id}")

        # Return pre-configured message for this contact if available
        if contact_id in self._messages:
            return self._messages[contact_id]

        # Return default message if configured
        if self._default_message:
            return self._default_message

        # Generate a simple fake message
        return ProspectMessage(
            subject=f"Opportunity for {contact.name or 'you'}",
            message=f"Hello {contact.name or 'there'},\n\n"
            f"I noticed your role at {company.name or 'your company'} and wanted to reach out. "
            f"As a {profile.job_title or 'professional'}, I believe we could have a great collaboration.\n\n"
            f"Best regards"
        )

    # Helper methods for test setup
    def set_message_for_contact(
        self, contact_id: str, message: ProspectMessage
    ) -> None:
        """Configure a specific message for a contact."""
        self._messages[contact_id] = message

    def set_default_message(self, message: ProspectMessage) -> None:
        """Set the default message to return."""
        self._default_message = message

    def set_should_fail_for(self, contact_id: str) -> None:
        """Configure a contact to trigger a failure."""
        self._should_fail_for.add(contact_id)

    def get_call_count(self) -> int:
        """Return the number of times get_message was called."""
        return self._call_count

    def clear(self) -> None:
        """Reset the fake port."""
        self._messages.clear()
        self._should_fail_for.clear()
        self._default_message = None
        self._call_count = 0
