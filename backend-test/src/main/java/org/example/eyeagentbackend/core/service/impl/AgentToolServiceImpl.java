package org.example.eyeagentbackend.core.service.impl;

import cn.dev33.satoken.util.SaResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.example.eyeagentbackend.core.dao.entity.activation.Activation;
import org.example.eyeagentbackend.core.dao.entity.hospital.*;
import org.example.eyeagentbackend.core.dao.entity.patient.Patient;
import org.example.eyeagentbackend.core.dao.entity.patient.UserPatient;
import org.example.eyeagentbackend.core.dao.entity.rbac.Doctor;
import org.example.eyeagentbackend.core.dao.entity.reserve.Agenda;
import org.example.eyeagentbackend.core.dao.entity.reserve.DoctorConfig;
import org.example.eyeagentbackend.core.dao.service.*;
import org.example.eyeagentbackend.core.dto.WorkingTimeSlot;
import org.example.eyeagentbackend.core.dto.request.agent.CreateReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.InitPatientReminderRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ModifyPatientReminderConfigRequest;
import org.example.eyeagentbackend.core.dto.request.agent.ReserveDoctorRequest;
import org.example.eyeagentbackend.core.dto.response.agent.*;
import org.example.eyeagentbackend.core.enums.AgendaClassify;
import org.example.eyeagentbackend.core.exceptions.agent.AgentException;
import org.example.eyeagentbackend.core.mq.dto.AgentReserveReminderMessage;
import org.example.eyeagentbackend.core.mq.producer.AgentOperationProducer;
import org.example.eyeagentbackend.core.redis.impl.AppointmentNumberServiceImpl;
import org.example.eyeagentbackend.core.service.AgentToolService;
import org.jetbrains.annotations.NotNull;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.*;
import java.util.stream.Collectors;

/**
 * @author chengyiyang
 */
@Service
@Slf4j
@RequiredArgsConstructor
public class AgentToolServiceImpl implements AgentToolService {

    private final IPatientService patientService;

    private final IPrescriptionService prescriptionService;

    private final IPrescriptionDetailService prescriptionDetailService;

    private final IAgendaService agendaService;

    private final IActivationService activationService;

    private final IDoctorActivateService doctorActivateService;

    private final IDoctorConfigService doctorConfigService;

    private final IDoctorWorkingDayService doctorWorkingDayService;

    private final IDoctorWorkingTimeService doctorWorkingTimeService;

    private final IDoctorService doctorService;

    private final IMedicalRecordService medicalRecordService;

    private final AgentOperationProducer agentOperationProducer;

    private final IUserPatientService userPatientService;

    private final AppointmentNumberServiceImpl appointmentNumberService;

    private final IReminderService reminderService;

    private final IReminderConfigService reminderConfigService;

    private final IBiomechanicsScanService biomechanicsScanService;

    @Override
    public SaResult getPatientPrescription(String patientId) {
        log.info("Patient {} 正在通过agent获取处方病例信息", patientId);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            List<Prescription> prescriptions = prescriptionService.listByPatientIdAsc(patientId);
            if (CollectionUtils.isEmpty(prescriptions)) {
                prescriptions = Collections.emptyList();
            }

            PatientPrescriptionResponse response = new PatientPrescriptionResponse();
            response.setPatient(patient);
            response.setPrescriptions(prescriptions);

            return SaResult.ok("获取患者处方成功")
                    .setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询患者处方信息失败, patientId={}", patientId, ex);
            throw new AgentException("查询患者处方信息失败，请稍后再试");
        }
    }

    @Override
    public SaResult getPatientPrescriptionLimit(String patientId, Integer limit) {
        log.info("Patient {} 正在通过agent获取最近 {} 份处方信息", patientId, limit);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            if (limit == null || limit <= 0) {
                throw new AgentException("获取数量必须大于0");
            }

            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            List<Prescription> prescriptions = prescriptionService.listByPatientIdDesc(patientId, limit);
            if (CollectionUtils.isEmpty(prescriptions)) {
                prescriptions = Collections.emptyList();
            }

            PatientPrescriptionResponse response = new PatientPrescriptionResponse();
            response.setPatient(patient);
            response.setPrescriptions(prescriptions);

            return SaResult.ok("获取患者最近处方成功")
                    .setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询患者最近处方信息失败, patientId={}, limit={}", patientId, limit, ex);
            throw new AgentException("查询患者处方信息失败，请稍后再试");
        }
    }

    @Override
    public SaResult getPatientPrescriptionDetail(String patientId, Integer limit) {
        log.info("Patient {} 正在通过agent获取最近 {} 份处方详细信息", patientId, limit);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            if (limit == null || limit <= 0) {
                throw new AgentException("获取数量必须大于0");
            }

            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            // 获取最近的N份处方
            List<Prescription> prescriptions = prescriptionService.listByPatientIdDesc(patientId, limit);
            if (CollectionUtils.isEmpty(prescriptions)) {
                PatientPrescriptionDetailResponse response = new PatientPrescriptionDetailResponse();
                response.setPatient(patient);
                response.setPrescriptions(Collections.emptyList());
                return SaResult.ok("获取患者处方详细信息成功").setData(response);
            }

            // 获取处方ID列表
            List<String> prescriptionIds = prescriptions.stream()
                    .map(Prescription::getId)
                    .toList();

            // 批量获取处方明细
            Map<String, List<PrescriptionDetail>> detailMap = prescriptionDetailService
                    .mapByPrescriptionIds(prescriptionIds);

            // 组装响应数据
            List<PrescriptionWithDetail> prescriptionWithDetails = prescriptions.stream()
                    .map(prescription -> {
                        PrescriptionWithDetail pwd = new PrescriptionWithDetail();
                        pwd.setPrescription(prescription);
                        pwd.setDetails(detailMap.getOrDefault(prescription.getId(), Collections.emptyList()));
                        return pwd;
                    })
                    .toList();

            PatientPrescriptionDetailResponse response = new PatientPrescriptionDetailResponse();
            response.setPatient(patient);
            response.setPrescriptions(prescriptionWithDetails);

            return SaResult.ok("获取患者处方详细信息成功").setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询患者处方详细信息失败, patientId={}, limit={}", patientId, limit, ex);
            throw new AgentException("查询患者处方详细信息失败，请稍后再试");
        }
    }

    @Override
    public SaResult getPatientReminder(String patientId, Integer limit) {
        log.info("Patient {} 正在通过agent获取最近 {} 条提醒信息", patientId, limit);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            if (limit == null || limit <= 0) {
                throw new AgentException("获取数量必须大于0");
            }

            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            List<Reminder> reminders = reminderService.listByPatientIdDesc(patientId, limit);
            if (CollectionUtils.isEmpty(reminders)) {
                reminders = Collections.emptyList();
            }

            Map<String, Object> response = new HashMap<>();
            response.put("patient", patient);
            response.put("reminders", reminders);

            return SaResult.ok("获取患者提醒信息成功").setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询患者提醒信息失败, patientId={}, limit={}", patientId, limit, ex);
            throw new AgentException("查询患者提醒信息失败，请稍后再试");
        }
    }

    @Override
    public SaResult getPatientReminderConfig(String patientId) {
        log.info("Patient {} 正在通过agent获取提醒配置", patientId);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            ReminderConfig config = reminderConfigService.getByPatientId(patientId);

            Map<String, Object> response = new HashMap<>();
            response.put("patient", patient);
            response.put("config", config);

            return SaResult.ok("获取患者提醒配置成功").setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询患者提醒配置失败, patientId={}", patientId, ex);
            throw new AgentException("查询患者提醒配置失败，请稍后再试");
        }
    }

    @Transactional
    @Override
    public SaResult initPatientReminderConfig(@NotNull InitPatientReminderRequest request) {
        String patientId = request.getPatientId();
        log.info("Patient {} 正在通过agent初始化提醒配置", patientId);
        try {
            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            ReminderConfig existingConfig = reminderConfigService.getByPatientId(patientId);
            if (existingConfig != null) {
                throw new AgentException("该患者已存在提醒配置，无法重复初始化");
            }

            ReminderConfig config = request.getConfig();
            config.setPatientId(patientId);
            reminderConfigService.save(config);

            return SaResult.ok("初始化患者提醒配置成功").setData(config);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("初始化患者提醒配置失败, patientId={}", patientId, ex);
            throw new AgentException("初始化患者提醒配置失败，请稍后再试");
        }
    }

    @Transactional
    @Override
    public SaResult modifyPatientReminderConfig(@NotNull ModifyPatientReminderConfigRequest request) {
        String patientId = request.getPatientId();
        log.info("Patient {} 正在通过agent修改提醒配置", patientId);
        try {
            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            ReminderConfig existingConfig = reminderConfigService.getByPatientId(patientId);
            if (existingConfig == null) {
                throw new AgentException("该患者不存在提醒配置，请先初始化");
            }

            ReminderConfig config = request.getConfig();
            config.setId(existingConfig.getId());
            config.setPatientId(patientId);
            reminderConfigService.updateById(config);

            return SaResult.ok("修改患者提醒配置成功").setData(config);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("修改患者提醒配置失败, patientId={}", patientId, ex);
            throw new AgentException("修改患者提醒配置失败，请稍后再试");
        }
    }

    @Override
    public SaResult getDoctorFreeTimeByDate(String patientId, @NotNull LocalDate date, String hospitalKey) {
        log.info("patient {} 正在通过agent获取 {} 在 {} 的空余时间信息", patientId,
                StringUtils.hasText(hospitalKey) ? hospitalKey : "所有医院", date);
        try {
            // 查找医院信息
            Activation hospitalInfo = activationService.getByHospital(hospitalKey);
            if (hospitalInfo == null) {
                List<Activation> activationList = activationService.listByHospitalKey(hospitalKey, 5);
                List<String> simpleHospitals = activationList.stream()
                        .map(Activation::getOrganizationName).toList();
                if (simpleHospitals.isEmpty()) {
                    throw AgentException.hospitalNotFound(hospitalKey);
                }
                throw AgentException.hospitalNotFound(hospitalKey, simpleHospitals);
            }

            // 获取医院中的医生信息
            String code = hospitalInfo.getOrganizationCode();
            List<Doctor> doctorList = doctorActivateService.listDoctorByCode(code);
            Map<String, Doctor> idDoctorMap = doctorList.stream()
                    .collect(Collectors.toMap(Doctor::getId, doctor -> doctor, (origin, duplicate) -> origin,
                            HashMap::new));
            List<String> doctorIds = idDoctorMap.keySet()
                    .stream().toList();
            if (CollectionUtils.isEmpty(doctorIds)) {
                throw AgentException.emptyDoctor(hospitalKey);
            }

            // 获取医生配置信息（只获取允许预约的医生）
            List<DoctorConfig> doctorConfigList = doctorConfigService.listByDoctorIds(doctorIds);
            Map<String, DoctorConfig> doctorIdConfigMap = doctorConfigList.stream()
                    .filter(DoctorConfig::getCanReserve)
                    .collect(
                            Collectors.toMap(DoctorConfig::getDoctorId, config -> config, (origin, duplicate) -> origin,
                                    HashMap::new));
            List<String> canReserveDoctorIds = new ArrayList<>(doctorIdConfigMap.keySet());
            if (CollectionUtils.isEmpty(canReserveDoctorIds)) {
                throw AgentException.canNotReserve(hospitalKey);
            }

            // 获取工作日配置，过滤掉当天不工作的医生
            // Java DayOfWeek: 1=周一...7=周日 → DB: 0=周日, 1=周一...6=周六
            int dayOfWeek = date.getDayOfWeek().getValue() % 7;
            Map<String, List<Byte>> workingDayMap = doctorWorkingDayService.mapByDoctorIds(canReserveDoctorIds);
            List<String> workingDoctorIds = canReserveDoctorIds.stream()
                    .filter(doctorId -> {
                        List<Byte> workingDays = workingDayMap.getOrDefault(doctorId, Collections.emptyList());
                        return workingDays.contains((byte) dayOfWeek);
                    })
                    .toList();
            if (CollectionUtils.isEmpty(workingDoctorIds)) {
                return SaResult.ok("该日期没有医生工作").setData(Collections.emptyList());
            }

            // 获取医生工作时间配置
            Map<String, List<WorkingTimeSlot>> workingTimeMap = doctorWorkingTimeService
                    .mapByDoctorIds(workingDoctorIds);

            // 获取指定日期的预约信息
            Map<String, List<Agenda>> agendaMap = agendaService.mapByUserIdsAndDate(workingDoctorIds, date);

            // 对每个医生计算空闲时间
            List<DoctorFreeTimeResponse> result = new ArrayList<>();
            for (String doctorId : workingDoctorIds) {
                List<WorkingTimeSlot> workingTimes = workingTimeMap.getOrDefault(doctorId, Collections.emptyList());
                List<Agenda> agendas = agendaMap.getOrDefault(doctorId, Collections.emptyList());
                DoctorConfig config = doctorIdConfigMap.get(doctorId);
                int reservePerHour = config.getReservePerHour() != null ? config.getReservePerHour() : 1;

                List<FreeTimeSlot> freeSlots = calculateFreeSlots(workingTimes, agendas, reservePerHour);

                if (!freeSlots.isEmpty()) {
                    DoctorFreeTimeResponse response = new DoctorFreeTimeResponse();
                    response.setDoctorId(doctorId);
                    response.setFreeSlots(freeSlots);
                    result.add(response);
                }
            }

            return SaResult.ok("获取医生空闲时间成功").setData(result);
        } catch (AgentException e) {
            throw e;
        } catch (Exception e) {
            log.error("获取医生空闲时间失败, patientId={}, date={}, hospitalKey={}", patientId, date, hospitalKey, e);
            throw new AgentException("获取医生空闲时间失败，请稍后再试");
        }
    }

    /**
     * 使用差分数组+前缀和算法计算空闲时间段
     *
     * @param workingTimes   工作时间段列表
     * @param agendas        已预约日程列表
     * @param reservePerHour 每小时可预约人数
     * @return 空闲时间段列表（包含容量）
     */
    private List<FreeTimeSlot> calculateFreeSlots(List<WorkingTimeSlot> workingTimes,
            List<Agenda> agendas,
            int reservePerHour) {
        if (CollectionUtils.isEmpty(workingTimes)) {
            return Collections.emptyList();
        }

        // 使用 TreeMap 实现稀疏差分数组
        TreeMap<Integer, Integer> diff = new TreeMap<>();

        // 标记工作时间 (+1)
        for (WorkingTimeSlot wt : workingTimes) {
            int start = toMinutes(wt.getStartTime());
            int end = toMinutes(wt.getEndTime());
            diff.merge(start, 1, Integer::sum);
            diff.merge(end, -1, Integer::sum);
        }

        // 标记已预约时间 (-1)
        for (Agenda agenda : agendas) {
            if (agenda.getStartTime() != null && agenda.getEndTime() != null) {
                int start = toMinutes(agenda.getStartTime().toLocalTime());
                int end = toMinutes(agenda.getEndTime().toLocalTime());
                diff.merge(start, -1, Integer::sum);
                diff.merge(end, 1, Integer::sum);
            }
        }

        // 遍历差分数组，计算前缀和，找出空闲区间
        List<FreeTimeSlot> result = new ArrayList<>();
        int current = 0;
        Integer slotStart = null;

        for (Map.Entry<Integer, Integer> entry : diff.entrySet()) {
            int prev = current;
            current += entry.getValue();
            int time = entry.getKey();

            if (prev <= 0 && current > 0) {
                // 空闲开始
                slotStart = time;
            } else if (prev > 0 && current <= 0 && slotStart != null) {
                // 空闲结束，计算容量
                int durationMinutes = time - slotStart;
                int capacity = (int) Math.floor((durationMinutes / 60.0) * reservePerHour);

                if (capacity > 0) {
                    result.add(new FreeTimeSlot(
                            toLocalTime(slotStart),
                            toLocalTime(time),
                            capacity));
                }
                slotStart = null;
            }
        }

        return result;
    }

    /**
     * 将 LocalTime 转换为分钟数
     */
    private int toMinutes(LocalTime time) {
        return time.getHour() * 60 + time.getMinute();
    }

    /**
     * 将分钟数转换为 LocalTime
     */
    private LocalTime toLocalTime(int minutes) {
        return LocalTime.of(minutes / 60, minutes % 60);
    }

    /**
     * 使用差分数组查找第一个可用的时间段
     *
     * @param rangeStart       查询范围开始时间
     * @param rangeEnd         查询范围结束时间
     * @param workingTimeSlots 工作时间段配置
     * @param existingAgendas  已有日程
     * @param requiredMinutes  需要的时长（分钟）
     * @return 第一个可用时段的开始时间，如果没有则返回 null
     */
    private LocalTime findFirstAvailableSlot(LocalTime rangeStart,
            LocalTime rangeEnd,
            List<WorkingTimeSlot> workingTimeSlots,
            List<Agenda> existingAgendas,
            int requiredMinutes) {
        int rangeStartMinutes = toMinutes(rangeStart);
        int rangeEndMinutes = toMinutes(rangeEnd);

        // 使用 TreeMap 实现稀疏差分数组
        TreeMap<Integer, Integer> diff = new TreeMap<>();

        // 标记工作时间 (+1)，只考虑与查询范围重叠的部分
        for (WorkingTimeSlot wt : workingTimeSlots) {
            int start = Math.max(toMinutes(wt.getStartTime()), rangeStartMinutes);
            int end = Math.min(toMinutes(wt.getEndTime()), rangeEndMinutes);
            if (start < end) {
                diff.merge(start, 1, Integer::sum);
                diff.merge(end, -1, Integer::sum);
            }
        }

        // 标记已占用时间 (-1)
        for (Agenda agenda : existingAgendas) {
            if (agenda.getStartTime() != null && agenda.getEndTime() != null) {
                int start = Math.max(toMinutes(agenda.getStartTime().toLocalTime()), rangeStartMinutes);
                int end = Math.min(toMinutes(agenda.getEndTime().toLocalTime()), rangeEndMinutes);
                if (start < end) {
                    diff.merge(start, -1, Integer::sum);
                    diff.merge(end, 1, Integer::sum);
                }
            }
        }

        // 遍历差分数组，找到第一个足够长的空闲时段
        int current = 0;
        Integer slotStart = null;

        for (Map.Entry<Integer, Integer> entry : diff.entrySet()) {
            int prev = current;
            current += entry.getValue();
            int time = entry.getKey();

            if (prev <= 0 && current > 0) {
                // 空闲开始
                slotStart = time;
            } else if (prev > 0 && current <= 0 && slotStart != null) {
                // 空闲结束，检查时长是否足够
                int durationMinutes = time - slotStart;
                if (durationMinutes >= requiredMinutes) {
                    return toLocalTime(slotStart);
                }
                slotStart = null;
            }
        }

        return null;
    }

    @Transactional
    @Override
    public SaResult reserveDoctor(@NotNull ReserveDoctorRequest request) {
        log.info("patient {} 正在通过agent预约医生 {}", request.getPatientId(), request.getDoctorId());
        try {
            // 标准化预约时间：只保留日期和小时，去掉分钟/秒/纳秒
            LocalDateTime hourStart = request.getReserveTime()
                    .withMinute(0).withSecond(0).withNano(0);

            // 基础校验
            if (!hourStart.isAfter(LocalDateTime.now().withMinute(0).withSecond(0).withNano(0))) {
                throw AgentException.reserveTimeError(hourStart);
            }

            Patient patient = patientService.getById(request.getPatientId());
            if (patient == null) {
                throw AgentException.patientNotFound(request.getPatientId());
            }

            Doctor doctor = doctorService.getById(request.getDoctorId());
            if (doctor == null) {
                throw AgentException.doctorNotFound(request.getDoctorId());
            }

            // 检查医生配置
            DoctorConfig doctorConfig = doctorConfigService.getByDoctorId(doctor.getId());
            if (doctorConfig == null || !Boolean.TRUE.equals(doctorConfig.getCanReserve())) {
                throw AgentException.doctorCanNotReserve(doctor.getId());
            }

            // 检查是否为医生的工作日
            // Java DayOfWeek: 1=周一...7=周日 → DB: 0=周日, 1=周一...6=周六
            int weekDay = hourStart.getDayOfWeek().getValue() % 7;
            List<Byte> workingDays = doctorWorkingDayService.listByDoctorId(doctor.getId());
            if (!workingDays.contains((byte) weekDay)) {
                throw AgentException.notWorkingDay(hourStart.toLocalDate());
            }

            // 检查该小时是否在工作时间内
            LocalTime hourLocalTime = hourStart.toLocalTime();
            List<WorkingTimeSlot> workingTimeSlots = doctorWorkingTimeService.listByDoctorId(doctor.getId());
            boolean withinWorkingHours = workingTimeSlots.stream()
                    .anyMatch(slot -> !hourLocalTime.isBefore(slot.getStartTime())
                            && hourLocalTime.isBefore(slot.getEndTime()));
            if (!withinWorkingHours) {
                throw AgentException.notWorkingTime(hourLocalTime);
            }

            // 获取配置：每小时可预约人数 & 每人诊断时长（分钟）
            int reservePerHour = doctorConfig.getReservePerHour() != null ? doctorConfig.getReservePerHour() : 1;
            int durationMinutes = 60 / reservePerHour;

            // 获取该小时内所有日程（包括医生自己的事务和患者预约）
            LocalDateTime hourEnd = hourStart.plusHours(1);
            List<Agenda> existingAgendas = agendaService.getAgendasByTimeRange(
                    doctor.getId(), hourStart, hourEnd);

            // 使用差分数组计算该小时内的空闲时间段
            LocalTime slotStart = findFirstAvailableSlot(
                    hourLocalTime,
                    hourLocalTime.plusHours(1),
                    workingTimeSlots,
                    existingAgendas,
                    durationMinutes);

            if (slotStart == null) {
                throw AgentException.noCapacity(hourStart);
            }

            // 计算预约时间
            LocalDateTime appointmentStart = hourStart.toLocalDate().atTime(slotStart);
            LocalDateTime appointmentEnd = appointmentStart.plusMinutes(durationMinutes);

            // 生成就诊号
            String visitCardNumber = appointmentNumberService.generateAppointmentNumber(LocalDate.now());

            // 保存病历信息
            MedicalRecord medicalRecord = request.getMedicalRecord();
            if (medicalRecord != null) {
                medicalRecord.setPatientId(patient.getId());
                medicalRecord.setVisitDate(appointmentStart);
                medicalRecord.setVisitTime(appointmentStart);
                medicalRecord.setVisitCardNumber(visitCardNumber);
                boolean recordSaved = medicalRecordService.save(medicalRecord);
                if (!recordSaved) {
                    throw new AgentException("病历保存失败，请稍后再试");
                }
            }

            // 创建预约日程
            Agenda agenda = new Agenda();
            agenda.setUserId(doctor.getId());
            agenda.setPatientId(patient.getId());
            agenda.setPatientName(patient.getPatientName());
            agenda.setTitle(String.format("患者 %s 预约就诊", patient.getPatientName()));
            agenda.setClassify(AgendaClassify.NORMAL);
            agenda.setStartTime(appointmentStart);
            agenda.setEndTime(appointmentEnd);
            agenda.setResolved(false);
            agenda.setStatus("PENDING");
            agenda.setCategory("APPOINTMENT");
            if (medicalRecord != null) {
                agenda.setMedicalRecordId(medicalRecord.getId());
            }

            boolean saved = agendaService.save(agenda);
            if (!saved) {
                throw new AgentException("预约保存失败，请稍后再试");
            }

            // 绑定患者到医生
            UserPatient existingUserPatient = userPatientService.getByUserIdAndPatientId(doctor.getId(),
                    patient.getId());
            if (existingUserPatient != null) {
                // 已存在绑定关系，只更新就诊号
                existingUserPatient.setVisitCardNumber(visitCardNumber);
                if (!userPatientService.updateById(existingUserPatient)) {
                    throw new AgentException("更新患者绑定关系失败");
                }
            } else {
                // 新建绑定关系
                UserPatient userPatient = new UserPatient();
                userPatient.setUserType("doctor");
                userPatient.setUserId(doctor.getId());
                userPatient.setPatientId(patient.getId());
                userPatient.setVisitCardNumber(visitCardNumber);
                if (!userPatientService.save(userPatient)) {
                    throw new AgentException("保存患者绑定关系失败");
                }
            }

            // 发送预约提醒消息
            AgentReserveReminderMessage reminderMessage = new AgentReserveReminderMessage();
            reminderMessage.setDoctorId(doctor.getId());
            reminderMessage.setPatientId(patient.getId());
            reminderMessage.setDoctorMessage(String.format("患者 %s 已预约 %s 就诊",
                    patient.getPatientName(), appointmentStart));
            reminderMessage.setPatientMessage(String.format("您已成功预约 %s 医生，就诊时间: %s",
                    doctor.getName(), appointmentStart));
            agentOperationProducer.sendAgentReserveReminder(reminderMessage);

            log.info("patient {} 成功预约医生 {}, 时间: {} - {}",
                    request.getPatientId(), request.getDoctorId(), appointmentStart, appointmentEnd);
            return SaResult.ok("预约成功").setData(agenda);

        } catch (AgentException e) {
            throw e;
        } catch (Exception e) {
            log.error("预约医生失败, request={}", request, e);
            throw new AgentException("预约失败，请稍后再试");
        }
    }

    @Override
    public SaResult createReminder(@NotNull CreateReminderRequest request) {
        String patientId = request.getPatientId();
        log.info("Patient {} 正在通过agent创建提醒", patientId);
        try {
            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            Reminder reminder = request.getReminder();
            reminder.setPatientId(patientId);
            reminderService.save(reminder);

            return SaResult.ok("创建患者提醒成功").setData(reminder);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("创建患者提醒失败, patientId={}", patientId, ex);
            throw new AgentException("创建患者提醒失败，请稍后再试");
        }
    }

    @Override
    public SaResult getPatientScanData(String medicalRecordId) {
        log.info("正在通过agent获取病历 {} 的生物力学扫描数据", medicalRecordId);
        try {
            if (!StringUtils.hasText(medicalRecordId)) {
                throw new AgentException("病历ID不能为空");
            }

            BiomechanicsScan scanData = biomechanicsScanService.getByMedicalRecordId(medicalRecordId);
            if (scanData == null) {
                throw new AgentException("未找到该病历对应的扫描数据");
            }

            return SaResult.ok("获取扫描数据成功").setData(scanData);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询扫描数据失败, medicalRecordId={}", medicalRecordId, ex);
            throw new AgentException("查询扫描数据失败，请稍后再试");
        }
    }

    @Override
    public SaResult getMedicalRecords(String patientId) {
        log.info("Patient {} 正在通过agent获取病历信息", patientId);
        try {
            if (!StringUtils.hasText(patientId)) {
                throw new AgentException("患者ID不能为空");
            }

            // 获取患者基本信息
            Patient patient = patientService.getById(patientId);
            if (patient == null) {
                throw new AgentException("未找到指定患者信息");
            }

            // 获取患者所有病历
            List<MedicalRecord> medicalRecords = medicalRecordService.lambdaQuery()
                    .eq(MedicalRecord::getPatientId, patientId)
                    .orderByDesc(MedicalRecord::getVisitDate)
                    .list();

            if (CollectionUtils.isEmpty(medicalRecords)) {
                medicalRecords = Collections.emptyList();
            }

            // 构建响应
            PatientMedicalRecordsResponse response = new PatientMedicalRecordsResponse();
            response.setPatient(patient);
            response.setMedicalRecords(medicalRecords);

            return SaResult.ok("获取病历信息成功").setData(response);
        } catch (AgentException ex) {
            throw ex;
        } catch (Exception ex) {
            log.error("查询病历信息失败, patientId={}", patientId, ex);
            throw new AgentException("查询病历信息失败，请稍后再试");
        }
    }
}
