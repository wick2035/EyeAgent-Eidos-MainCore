package org.example.eyeagentbackend.controller;

import cn.dev33.satoken.util.SaResult;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.example.eyeagentbackend.core.dto.request.agent.CreateReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.InitPatientReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ModifyPatientReminderConfigRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ReserveDoctorRequest;
import org.example.eyeagentbackend.core.service.AgentToolService;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;

/**
 * Agent工具控制器 - 提供AI Agent调用的各类接口
 *
 * @author chengyiyang
 */
@RestController
@RequestMapping("/agent/api")
@RequiredArgsConstructor
public class AgentToolController {

    private final AgentToolService agentToolService;

    // ==================== Agent 1: 预约相关接口 ====================

    /**
     * 获取患者所有处方信息
     *
     * @param patientId 患者ID
     * @return PatientPrescriptionResponse
     */
    @GetMapping("/patient-prescription")
    public SaResult getPatientPrescription(@RequestParam String patientId) {
        return agentToolService.getPatientPrescription(patientId);
    }

    /**
     * 获取指定日期医生的空闲时间段
     *
     * @param patientId   患者ID
     * @param date        查询日期 (yyyy-MM-dd)
     * @param hospitalKey 医院关键字
     * @return List&lt;DoctorFreeTimeResponse&gt;
     */
    @GetMapping("/doctor-free-time")
    public SaResult getDoctorFreeTimeByDate(@RequestParam String patientId, @RequestParam @NotNull LocalDate date,
            @RequestParam String hospitalKey) {
        return agentToolService.getDoctorFreeTimeByDate(patientId, date, hospitalKey);
    }

    /**
     * 预约医生
     *
     * @param request ReserveDoctorRequest
     * @return Agenda
     */
    // todo check record_id return
    @PostMapping("/reserve-doctor")
    public SaResult reserveDoctor(@Valid @RequestBody ReserveDoctorRequest request) {
        return agentToolService.reserveDoctor(request);
    }

    // ==================== Agent 2: 处方与扫描数据接口 ====================

    /**
     * 获取患者最近N份处方
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return PatientPrescriptionResponse
     */
    @GetMapping("/patient-prescription-limit")
    public SaResult getPatientPrescriptionLimit(@RequestParam String patientId, @RequestParam Integer limit) {
        return agentToolService.getPatientPrescriptionLimit(patientId, limit);
    }

    /**
     * 获取患者最近N份处方及详细药品信息
     *
     * @param patientId 患者ID
     * @param limit     限制数量
     * @return PatientPrescriptionDetailResponse
     */
    @GetMapping("/patient-prescription-detail")
    public SaResult getPatientPrescriptionDetail(@RequestParam String patientId, @RequestParam Integer limit) {
        return agentToolService.getPatientPrescriptionDetail(patientId, limit);
    }

    /**
     * 获取患者生物力学扫描数据
     *
     * @param medicalRecordId 病历ID
     * @return BiomechanicsScan
     */
    @GetMapping("/patient-scan-data")
    public SaResult getPatientScanData(@RequestParam String medicalRecordId) {
        return agentToolService.getPatientScanData(medicalRecordId);
    }

    /**
     * 生成病历PDF报告
     *
     * @param medicalRecordId 病历ID
     * @return String (PDF文件路径)
     */
    @PostMapping("/generate-medical-record-pdf")
    public SaResult generateMedicalRecordPdf(@RequestParam String medicalRecordId) {
        return SaResult.ok("正在开发...");
    }

    /**
     * 生成处方PDF报告
     *
     * @param medicalRecordId 病历ID
     * @return String (PDF文件路径)
     */
    @PostMapping("/generate-prescription-pdf")
    public SaResult generatePrescriptionPdf(@RequestParam String medicalRecordId) {
        return SaResult.ok("正在开发...");
    }

    // ==================== Agent 3: 提醒管理接口 ====================

    /**
     * 获取患者最近的提醒信息
     *
     * @param patientId 患者ID
     * @param limit     限制数量，默认5条
     * @return {patient: Patient, reminders: List&lt;Reminder&gt;}
     */
    @GetMapping("/patient-reminder")
    public SaResult getPatientReminder(@RequestParam String patientId,
            @RequestParam(defaultValue = "5") Integer limit) {
        return agentToolService.getPatientReminder(patientId, limit);
    }

    /**
     * 获取患者的提醒配置
     *
     * @param patientId 患者ID
     * @return {patient: Patient, config: ReminderConfig}
     */
    @GetMapping("/patient-reminder-config")
    public SaResult getPatientReminderConfig(@RequestParam String patientId) {
        return agentToolService.getPatientReminderConfig(patientId);
    }

    /**
     * 初始化患者提醒配置（仅限首次创建）
     *
     * @param request InitPatientReminderRequest
     * @return ReminderConfig
     */
    @PostMapping("/init-patient-reminder-config")
    public SaResult initPatientReminderConfig(@Valid @RequestBody InitPatientReminderRequest request) {
        return agentToolService.initPatientReminderConfig(request);
    }

    /**
     * 修改患者提醒配置
     *
     * @param request ModifyPatientReminderConfigRequest
     * @return ReminderConfig
     */
    @PostMapping("/modify-patient-reminder-config")
    public SaResult modifyPatientReminderConfig(@Valid @RequestBody ModifyPatientReminderConfigRequest request) {
        return agentToolService.modifyPatientReminderConfig(request);
    }

    /**
     * 创建患者提醒
     *
     * @param request CreateReminderRequest
     * @return Reminder
     */
    @PostMapping("/create-reminder")
    public SaResult createReminder(@Valid @RequestBody CreateReminderRequest request) {
        return agentToolService.createReminder(request);
    }

    // ==================== 患者信息相关接口 ====================

    /**
     * 获取患者病历列表（用于Agent加载患者历史病史信息）
     *
     * @param patientId 患者ID
     * @return {patient: Patient, medicalRecords: List&lt;MedicalRecord&gt;}
     */
    @GetMapping("/get-medical-record")
    public SaResult getMedicalRecords(@RequestParam String patientId) {
        return agentToolService.getMedicalRecords(patientId);
    }

}
