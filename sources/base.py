from abc import ABC, abstractmethod
from models.financials import CompanyFinancials


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, identifier: str) -> str:
        """Resolve a ticker / company number / name → internal source ID."""

    @abstractmethod
    def search(self, name: str) -> list[dict]:
        """Return a list of matching companies: [{id, name, ...}]."""

    @abstractmethod
    def get_financials(self, identifier: str) -> CompanyFinancials:
        """Full pipeline: lookup → fetch → parse → return structured data."""
