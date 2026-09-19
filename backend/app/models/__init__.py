"""V-SHIELD AI Models Package (AASIST & ECAPA-TDNN)."""

from app.models.aasist import Model as AASISTModel
from app.models.aasist_service import AASISTService
from app.models.ecapa_service import ECAPAService

__all__ = ["AASISTModel", "AASISTService", "ECAPAService"]
