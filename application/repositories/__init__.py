"""
仓储接口定义
"""
from application.repositories.patient_repository import IPatientRepository
from application.repositories.appointment_repository import IAppointmentRepository
from application.repositories.prescription_repository import IPrescriptionRepository

__all__ = [
    "IPatientRepository",
    "IAppointmentRepository",
    "IPrescriptionRepository",
]

