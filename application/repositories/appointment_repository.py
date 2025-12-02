"""
预约仓储接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from domain.models.appointment import Appointment


class IAppointmentRepository(ABC):
    """预约仓储接口"""
    
    @abstractmethod
    def get_by_id(self, appointment_id: str) -> Optional[Appointment]:
        """
        根据ID获取预约
        
        Args:
            appointment_id: 预约UUID
        
        Returns:
            Appointment对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def get_by_patient(self, patient_id: str, limit: int = 10) -> List[Appointment]:
        """
        获取患者的预约列表
        
        Args:
            patient_id: 患者UUID
            limit: 限制数量
        
        Returns:
            Appointment对象列表
        """
        pass
    
    @abstractmethod
    def get_doctor_free_time(self, patient_id: str, date: str, 
                            hospital_key: str) -> dict:
        """
        获取医生空闲时间
        
        Args:
            patient_id: 患者UUID
            date: 日期字符串 yyyy-MM-dd
            hospital_key: 医院关键字
        
        Returns:
            包含空闲时间段和医生信息的字典
        """
        pass
    
    @abstractmethod
    def create(self, appointment: Appointment) -> Appointment:
        """
        创建预约
        
        Args:
            appointment: Appointment对象
        
        Returns:
            创建后的Appointment对象
        """
        pass
    
    @abstractmethod
    def cancel(self, appointment_id: str) -> bool:
        """
        取消预约
        
        Args:
            appointment_id: 预约UUID
        
        Returns:
            是否取消成功
        """
        pass

