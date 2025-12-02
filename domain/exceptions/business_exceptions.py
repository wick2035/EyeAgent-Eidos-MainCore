"""
业务异常定义
"""


class DomainException(Exception):
    """领域异常基类"""
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code or "DOMAIN_ERROR"
        super().__init__(self.message)


class PatientNotFoundError(DomainException):
    """患者不存在异常"""
    
    def __init__(self, patient_id: str):
        message = f"患者不存在: {patient_id}"
        super().__init__(message, "PATIENT_NOT_FOUND")
        self.patient_id = patient_id


class InvalidAppointmentError(DomainException):
    """无效预约异常"""
    
    def __init__(self, message: str):
        super().__init__(message, "INVALID_APPOINTMENT")


class AppointmentConflictError(DomainException):
    """预约冲突异常"""
    
    def __init__(self, message: str):
        super().__init__(message, "APPOINTMENT_CONFLICT")


class PrescriptionNotFoundError(DomainException):
    """处方不存在异常"""
    
    def __init__(self, prescription_id: str):
        message = f"处方不存在: {prescription_id}"
        super().__init__(message, "PRESCRIPTION_NOT_FOUND")
        self.prescription_id = prescription_id


class ReminderNotFoundError(DomainException):
    """提醒不存在异常"""
    
    def __init__(self, reminder_id: str):
        message = f"提醒不存在: {reminder_id}"
        super().__init__(message, "REMINDER_NOT_FOUND")
        self.reminder_id = reminder_id


class InvalidStageTransitionError(DomainException):
    """无效阶段转换异常"""
    
    def __init__(self, from_stage: str, to_stage: str):
        message = f"无效的阶段转换: {from_stage} -> {to_stage}"
        super().__init__(message, "INVALID_STAGE_TRANSITION")
        self.from_stage = from_stage
        self.to_stage = to_stage

