"""
Contact validation module for the enrich leads agent.

Provides validation services for extracted contacts to ensure data quality.
"""

from infrastructure.services.enrich_leads_agent.validators.contact_validator import (
    ContactValidator,
)

__all__ = ["ContactValidator"]
