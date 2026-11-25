"""M06 RAG Dossier / Execution facade domain errors."""

from __future__ import annotations


class EvaluationError(RuntimeError):
    """Base error for RAG Lab evaluation/dossier use cases."""


class DossierNotFound(EvaluationError):
    """The requested RAG Dossier does not exist."""


class DossierArchived(EvaluationError):
    """An archived Dossier cannot start new execution."""


class RunNotFound(EvaluationError):
    """The requested Execution Run does not exist."""


class UnsupportedDossierRunKind(EvaluationError):
    """The requested Dossier run kind is not supported in M1-A."""


class InvalidDossierRunParams(EvaluationError):
    """The requested Dossier run parameters are invalid."""
