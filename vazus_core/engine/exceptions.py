"""
vazus_core.exceptions — Unified Exception Taxonomy for Vazus SuperGraph OS v4.0.
"""

class VazusBaseException(Exception):
    """Base exception for all Vazus SuperGraph OS errors."""
    pass

class DatabaseLockError(VazusBaseException):
    """Raised when SQLite database lock cannot be acquired within timeout."""
    pass

class EmbeddingError(VazusBaseException):
    """Raised when 768D vector embedding computation fails."""
    pass

class JuryConsensusError(VazusBaseException):
    """Raised when Concordia Multi-Agent Jury consensus threshold (<66%) fails."""
    pass

class SMTVerificationError(VazusBaseException):
    """Raised when SMT Z3 contract proof verification fails."""
    pass

class SubagentExecutionError(VazusBaseException):
    """Raised when a subagent REPL or bridge execution fails."""
    pass

class SessionRequiredError(VazusBaseException):
    """Raised when authentication session tokens are absent or expired (Fail-Closed)."""
    pass

class ScheduleFetchError(VazusBaseException):
    """Raised when schedule fetching fails from authoritative endpoint (Fail-Closed)."""
    pass
