"""
处方仓储接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models.prescription import Prescription


class IPrescriptionRepository(ABC):
    """处方仓储接口"""
    
    @abstractmethod
    def get_by_id(self, prescription_id: str) -> Optional[Prescription]:
        """
        根据ID获取处方
        
        Args:
            prescription_id: 处方UUID
        
        Returns:
            Prescription对象，如果不存在则返回None
        """
        pass
    
    @abstractmethod
    def get_by_patient(self, patient_id: str, limit: int = 10) -> List[Prescription]:
        """
        获取患者的处方列表
        
        Args:
            patient_id: 患者UUID
            limit: 限制数量
        
        Returns:
            Prescription对象列表
        """
        pass
    
    @abstractmethod
    def get_by_patient_with_details(self, patient_id: str, 
                                    limit: int = 10) -> List[Prescription]:
        """
        获取患者的处方列表（包含详细药品信息）
        
        Args:
            patient_id: 患者UUID
            limit: 限制数量
        
        Returns:
            包含详细信息的Prescription对象列表
        """
        pass
    
    @abstractmethod
    def create(self, prescription: Prescription) -> Prescription:
        """
        创建处方
        
        Args:
            prescription: Prescription对象
        
        Returns:
            创建后的Prescription对象
        """
        pass

