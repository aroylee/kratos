"""Kratos Auto-Ontology Package.

Provides automated schema introspection, semantic entity/relationship extraction,
and epistemological answerability validation for Text-to-SQL workflows.
"""

from kratos.ontology.auto_ontology import (
    AutoOntologyExtractor,
    AutoOntologyService,
    CANONICAL_SYNONYM_RULES,
)
from kratos.ontology.grounder import (
    AutoOntologyGrounder,
    AnswerabilityResult,
    GroundingContext,
)

__all__ = [
    "AutoOntologyExtractor",
    "AutoOntologyService",
    "CANONICAL_SYNONYM_RULES",
    "AutoOntologyGrounder",
    "AnswerabilityResult",
    "GroundingContext",
]
