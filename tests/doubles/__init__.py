"""Test doubles (fakes) for unit testing."""

from tests.doubles.repositories import (
    FakeCampaignRepository,
    FakeProfileRepository,
)
from tests.doubles.ports import FakeGenerateMessagePort

__all__ = [
    "FakeCampaignRepository",
    "FakeProfileRepository",
    "FakeGenerateMessagePort",
]
