package org.example.eyeagentbackend.core.service;

import cn.dev33.satoken.util.SaResult;
import org.example.eyeagentbackend.core.dto.request.agent.CreateReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.InitPatientReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ModifyPatientReminderConfigRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ReserveDoctorRequest;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;

public interface AgentToolService {
    SaResult getPatientPrescription(String patientId);

    /**
     * 获取患者最近的N份处方
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return 处方列表
     */
    SaResult getPatientPrescriptionLimit(String patientId, Integer limit);

    /**
     * 获取患者最近的N份处方及详细药品信息
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return 处方及详细信息列表
     */
    SaResult getPatientPrescriptionDetail(String patientId, Integer limit);

    /**
     * 获取患者的提醒信息
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return 提醒列表
     */
    SaResult getPatientReminder(String patientId, Integer limit);

    /**
     * 获取患者的提醒配置
     *
     * @param patientId 患者ID
     * @return 提醒配置
     */
    SaResult getPatientReminderConfig(String patientId);

    /**
     * 初始化患者提醒配置（仅限首次创建，已存在则抛出异常）
     *
     * @param request 请求参数
     * @return 操作结果
     */
    SaResult initPatientReminderConfig(InitPatientReminderRequest request);

    /**
     * 修改患者提醒配置（配置不存在则抛出异常）
     *
     * @param request 请求参数
     * @return 操作结果
     */
    SaResult modifyPatientReminderConfig(ModifyPatientReminderConfigRequest request);

    SaResult getDoctorFreeTimeByDate(String patientId, LocalDate date, String hospitalKey);

    @Transactional
    SaResult reserveDoctor(ReserveDoctorRequest request);

    /**
     * 创建患者提醒
     *
     * @param request 请求参数
     * @return 操作结果
     */
    SaResult createReminder(CreateReminderRequest request);

    /**
     * 获取患者生物力学扫描数据
     *
     * @param medicalRecordId 病历ID
     * @return 扫描数据
     */
    SaResult getPatientScanData(String medicalRecordId);

    /**
     * 获取患者病历列表（包含患者基本信息）
     *
     * @param patientId 患者ID
     * @return {patient: Patient, medicalRecords: List<MedicalRecord>}
     */
    SaResult getMedicalRecords(String patientId);
}
