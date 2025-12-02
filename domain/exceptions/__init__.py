"""
领域异常
"""
from domain.exceptions.business_exceptions import (
    DomainException,
    PatientNotFoundError,
    InvalidAppointmentError,
    AppointmentConflictError,
    PrescriptionNotFoundError,
    ReminderNotFoundError,
    InvalidStageTransitionError,
)

__all__ = [
    "DomainException",
    "PatientNotFoundError",
    "InvalidAppointmentError",
    "AppointmentConflictError",
    "PrescriptionNotFoundError",
    "ReminderNotFoundError",
    "InvalidStageTransitionError",
]

