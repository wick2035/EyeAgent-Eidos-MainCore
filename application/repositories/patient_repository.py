"""
患者仓储接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models.patient import Patient


class IPatientRepository(ABC):
    """患者仓储接口"""
    
    @abstractmethod
    def get_by_id(self, patient_id: str) -> Optional[Patient]:
        """
        根据ID获取患者
        
        Args:
            patient_id: 患者UUID
        
        Returns:
            Patient对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def get_by_phone(self, phone: str) -> Optional[Patient]:
        """
        根据手机号获取患者
        
        Args:
            phone: 手机号
        
        Returns:
            Patient对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def create(self, patient: Patient) -> Patient:
        """
        创建患者
        
        Args:
            patient: Patient对象
        
        Returns:
            创建后的Patient对象
        """
        pass
    
    @abstractmethod
    def update(self, patient: Patient) -> Patient:
        """
        更新患者信息
        
        Args:
            patient: Patient对象
        
        Returns:
            更新后的Patient对象
        """
        pass

