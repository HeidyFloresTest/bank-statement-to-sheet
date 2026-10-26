"""Abstract base extractor interface for statement parsers."""

from abc import ABC, abstractmethod

from app.schemas import TransactionItem


class BaseExtractor(ABC):
    """Abstract interface defining the statement extraction contract."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> list[TransactionItem]:
        """Extract normalized transactions from raw statement bytes.

        :param file_bytes: Raw binary content of the file.
        :param filename: Original name of the uploaded statement.
        :return: List of normalized TransactionItem instances.
        """
        raise NotImplementedError
