package org.example.eyeagentbackend.core.exceptions.agent;

import org.example.eyeagentbackend.core.exceptions.BusinessException;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;

/**
 * @author chengyiyang
 */
public class AgentException extends BusinessException {
    public AgentException(String message) {
        super(message);
    }

    public static AgentException hospitalNotFound(String hospitalKey) {
        return new AgentException(hospitalKey + "未找到");
    }

    public static AgentException hospitalNotFound(String hospitalKey, List<String> simpleHospitals) {
        return new AgentException(hospitalKey + "未找到。相似的医院还有：" + simpleHospitals);
    }

    public static AgentException emptyDoctor(String hospital) {
        return new AgentException(hospital + " 暂无医生");
    }

    public static AgentException canNotReserve(String hospital) {
        return new AgentException(hospital + " 中没有可预约的医生");
    }

    public static AgentException reserveTimeError(LocalDateTime time) {
        return new AgentException("预约时间 " + time + " 比当前时间早");
    }

    public static AgentException patientNotFound(String patientId) {
        return new AgentException(String.format("Patient %s 不存在", patientId));
    }

    public static AgentException doctorNotFound(String doctorId) {
        return new AgentException(String.format("Doctor %s 不存在", doctorId));
    }

    public static AgentException doctorCanNotReserve(String doctorId) {
        return new AgentException(String.format("医生 %s 暂未开放预约", doctorId));
    }

    public static AgentException notWorkingDay(LocalDate date) {
        return new AgentException(String.format("%s 不是医生的工作日", date));
    }

    public static AgentException notWorkingTime(LocalTime time) {
        return new AgentException(String.format("%s 不在医生的工作时间内", time));
    }

    public static AgentException noCapacity(LocalDateTime time) {
        return new AgentException(String.format("%s 时段预约已满", time));
    }
}
