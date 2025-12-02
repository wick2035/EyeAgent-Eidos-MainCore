"""
领域模型
"""
from domain.models.patient import Patient
from domain.models.appointment import Appointment
from domain.models.medical_record import MedicalRecord
from domain.models.prescription import Prescription
from domain.models.conversation import Conversation, Message

__all__ = [
    "Patient",
    "Appointment",
    "MedicalRecord",
    "Prescription",
    "Conversation",
    "Message",
]

