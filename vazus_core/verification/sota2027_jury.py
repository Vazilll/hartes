"""
vazus_core.sota2027_jury — Compatibility bridge mapping SOTA2027JuryEngine to ConcordiaJury.
"""
from vazus_core.verification.concordia_jury import ConcordiaJury as SOTA2027JuryEngine, JuryVerdict, ConcordiaJury

__all__ = ["SOTA2027JuryEngine", "JuryVerdict", "ConcordiaJury"]
