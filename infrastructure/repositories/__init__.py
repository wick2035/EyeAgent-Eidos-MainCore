"""
仓储实现
"""
from infrastructure.repositories.patient_repository_impl import PatientRepositoryImpl
from infrastructure.repositories.appointment_repository_impl import AppointmentRepositoryImpl
from infrastructure.repositories.prescription_repository_impl import PrescriptionRepositoryImpl

__all__ = [
    "PatientRepositoryImpl",
    "AppointmentRepositoryImpl",
    "PrescriptionRepositoryImpl",
]

