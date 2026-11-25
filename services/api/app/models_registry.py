"""Import all ORM models so SQLAlchemy and Alembic can see the full schema."""

from app.modules.artifact.models import Artifact  # noqa: F401
from app.modules.capture.models import Capture, RawContent  # noqa: F401
from app.modules.chat.models import ChatMessage, Conversation  # noqa: F401
from app.modules.dossier.models import Dossier, DossierAsset  # noqa: F401
from app.modules.evaluation.models import RagDossier  # noqa: F401
from app.modules.execution.models import (  # noqa: F401
    ExecutionEvent,
    ExecutionJob,
    ExecutionJobAttempt,
    ExecutionRun,
    ExecutionStep,
)
from app.modules.knowledge.models import (  # noqa: F401
    AssetVersion,
    Draft,
    DraftRevision,
    KnowledgeAsset,
    PublishRecord,
)
from app.modules.page.models import Page, PageVersion  # noqa: F401
