# 语音识别（ASR）接口文档

**系统版本**：3.0.0
**服务地址**：`http://{host}:20602`
**底层模型**：`qwen3-asr-flash-realtime-2026-02-10`（阿里云 DashScope，OpenAI Realtime API 兼容协议）
**接口数量**：2 个（HTTP + WebSocket）

---

## 目录

1. [音频规格要求](#1-音频规格要求)
2. [接口一：HTTP 文件上传（`POST /api/asr/transcribe`）](#2-接口一http-文件上传)
3. [接口二：WebSocket 实时流式（`WS /ws/asr`）](#3-接口二websocket-实时流式)
4. [错误码定义](#4-错误码定义)
5. [接口选型建议](#5-接口选型建议)
6. [完整调用示例](#6-完整调用示例)

---

## 1. 音频规格要求

无论使用哪个接口，发送到本服务的音频**必须满足以下规格**。本服务不做采样率转换，格式不符将导致识别失败或乱码。

| 参数 | 要求 | 说明 |
|------|------|------|
| 编码格式 | PCM（线性脉冲编码调制） | 16-bit 有符号整数，**小端序**（Little Endian） |
| 采样率 | **16000 Hz** | 必须是 16kHz，不接受 8kHz / 44.1kHz 等 |
| 声道数 | **单声道（Mono）** | 不接受立体声 |
| 最短时长 | **0.5 秒** | PCM 字节数 ≥ 16000 bytes（0.5s × 16000Hz × 2bytes） |
| 封装格式 | HTTP 接口：WAV（RIFF 头 + PCM 数据）<br>WebSocket 接口：裸 PCM 字节 | - |

**WAV 文件说明**：HTTP 接口只接受标准 WAV（RIFF 格式），服务会用 Python `wave` 模块提取内部 PCM 数据再送识别。WAV 本身的采样率字段**不会被验证也不会转换**，请确保录制时就是 16kHz。

---

## 2. 接口一：HTTP 文件上传

**适用场景**：录音完毕后一次性上传整段音频（如按住说话 Push-to-Talk 场景）。

### 2.1 基本信息

```
POST /api/asr/transcribe
Content-Type: multipart/form-data
```

### 2.2 请求参数

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|--------|------|------|------|------|
| `audio` | Body（multipart） | File | 是 | WAV 格式音频文件（16kHz, mono, 16-bit PCM） |

**注意**：当前实现语言固定为 `zh`（中文），如需多语言支持请联系后端扩展接口。

### 2.3 成功响应

**HTTP 200**

```json
{
  "text": "识别出的文字内容"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `text` | string | 语音识别文字，已去除首尾空白，非空字符串 |

### 2.4 失败响应

**HTTP 400 / 500 / 502**

```json
{
  "detail": {
    "error_code": "NO_SPEECH_DETECTED",
    "message": "未检测到语音，请说话后再松开按钮"
  }
}
```

> FastAPI 的 `HTTPException.detail` 包含结构化错误对象，字段见第 4 节错误码定义。

### 2.5 HTTP 状态码对照

| HTTP 状态码 | 触发条件 |
|-------------|---------|
| 200 | 识别成功 |
| 400 | 文件为空 / WAV 格式错误 / 音频过短 / 未检测到语音 |
| 500 | 服务端配置错误或内部异常 |
| 502 | DashScope ASR 上游服务异常 |

### 2.6 调用示例

**curl**

```bash
curl -X POST http://localhost:20602/api/asr/transcribe \
  -F "audio=@recording.wav;type=audio/wav"
```

**Python（requests）**

```python
import requests

with open("recording.wav", "rb") as f:
    resp = requests.post(
        "http://localhost:20602/api/asr/transcribe",
        files={"audio": ("recording.wav", f, "audio/wav")},
    )

if resp.status_code == 200:
    print(resp.json()["text"])
else:
    error = resp.json().get("detail", {})
    print(f"错误 {error.get('error_code')}: {error.get('message')}")
```

**Java（OkHttp）**

```java
OkHttpClient client = new OkHttpClient();

RequestBody body = new MultipartBody.Builder()
    .setType(MultipartBody.FORM)
    .addFormDataPart(
        "audio",
        "recording.wav",
        RequestBody.create(wavBytes, MediaType.parse("audio/wav"))
    )
    .build();

Request request = new Request.Builder()
    .url("http://localhost:20602/api/asr/transcribe")
    .post(body)
    .build();

try (Response response = client.newCall(request).execute()) {
    String json = response.body().string();
    // 解析 {"text": "..."}
}
```

---

## 3. 接口二：WebSocket 实时流式

**适用场景**：其他后端系统实时流式传输音频，按会话发起识别任务。

### 3.1 基本信息

```
WebSocket ws://{host}:20602/ws/asr
```

无需请求头认证（API Key 由服务端持有），直接建立 WebSocket 连接即可。

### 3.2 完整会话时序

```
客户端                                      服务端
  │                                            │
  ├── 建立 WebSocket 连接 ───────────────────→ │
  │                                            │
  ├── 发 JSON: {"event":"start",...} ────────→ │
  │                                            │
  │ ←─ 发 JSON: {"event":"started",...} ──────┤
  │                                            │
  ├── 发 Binary: PCM 帧 1 ─────────────────→  │
  ├── 发 Binary: PCM 帧 2 ─────────────────→  │
  ├── 发 Binary: PCM 帧 N ─────────────────→  │
  │                                            │  （帧可随采集进度持续发送，无需一次性全发）
  │                                            │
  ├── 发 JSON: {"event":"stop"} ───────────→  │
  │                                            │  （服务端开始调用 DashScope 识别）
  │                                            │
  │ ←─ 发 JSON: {"event":"result","is_final":true,...} ──┤
  │ ←─ 发 JSON: {"event":"done",...} ─────────┤
  │                                            │
  ├── [可继续下一轮 start/audio/stop] ──────→  │
  │   或断开连接                                │
```

**一个 WebSocket 连接可承载多轮识别任务**，每轮以 `start` 开始、`done` 或 `error` 结束。

### 3.3 客户端 → 服务端消息

#### 3.3.1 开始任务（必须首先发送）

**帧类型**：Text（JSON）

```json
{
  "event": "start",
  "request_id": "req-20240308-001",
  "language": "zh"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `event` | string | 是 | — | 固定值 `"start"` |
| `request_id` | string | 否 | null | 调用方自定义追踪 ID，原样回传到所有响应消息，方便日志关联 |
| `language` | string | 否 | `"zh"` | 识别语言，目前支持 `"zh"`（中文）、`"en"`（英文）等 |

#### 3.3.2 发送音频数据

**帧类型**：Binary（裸字节）

发送原始 PCM 字节，格式要求见第 1 节。

- 每帧建议大小：**3200 bytes**（100ms 的音频），最大不超过 65536 bytes
- 发送时机：收到 `started` 响应后即可持续发送
- 不需要 JSON 包装，直接发送二进制数据

```
// 伪代码
while recording:
    chunk = mic.read(3200)  // 100ms PCM
    ws.send_bytes(chunk)
```

#### 3.3.3 结束任务（触发识别）

**帧类型**：Text（JSON）

```json
{
  "event": "stop"
}
```

发送 `stop` 后，服务端停止接收音频，调用 DashScope ASR 对已缓冲的全部音频进行识别，然后返回 `result` + `done`。

> **重要**：`stop` 发送后，服务端会对**已收到的全部音频**一次性识别，而不是只识别最后一帧。请确保所有音频帧都已发送完毕再发 `stop`。

### 3.4 服务端 → 客户端消息

所有服务端消息均为 **Text 帧（JSON）**。

#### 3.4.1 任务已启动

```json
{
  "event": "started",
  "request_id": "req-20240308-001"
}
```

收到此消息后，客户端可开始发送音频二进制帧。

#### 3.4.2 识别结果

```json
{
  "event": "result",
  "request_id": "req-20240308-001",
  "text": "识别出的文字内容",
  "is_final": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `event` | string | 固定值 `"result"` |
| `request_id` | string/null | 原样回传 |
| `text` | string | 当前识别文字 |
| `is_final` | bool | 当前版本始终为 `true`（仅发一次最终结果） |

> 当前实现在 `stop` 后批量识别，不发送 `is_final: false` 的中间结果。后续版本可扩展为实时流式中间结果。

#### 3.4.3 任务完成

```json
{
  "event": "done",
  "request_id": "req-20240308-001",
  "text": "识别出的文字内容"
}
```

收到 `done` 代表本轮识别任务结束，`text` 与前一条 `result` 的 `text` 相同。收到 `done` 后客户端可继续发起下一轮（再发 `start`）或关闭连接。

#### 3.4.4 错误

```json
{
  "event": "error",
  "request_id": "req-20240308-001",
  "error_code": "NO_SPEECH_DETECTED",
  "message": "未检测到语音"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `event` | string | 固定值 `"error"` |
| `request_id` | string/null | 原样回传 |
| `error_code` | string | 见第 4 节错误码定义 |
| `message` | string | 人类可读的错误描述（中文） |

出现 `error` 后，本轮任务终止。若错误码为 `INTERNAL_ERROR` / `ASR_API_ERROR`，建议等待 1-2 秒后重试；若为 `AUDIO_TOO_SHORT` / `NO_SPEECH_DETECTED`，属于业务逻辑问题，不需要重连。

---

## 4. 错误码定义

| error_code | 适用接口 | 触发条件 | 建议处理 |
|------------|---------|---------|---------|
| `NO_SPEECH_DETECTED` | HTTP / WS | 音频中未检测到有效语音（静音或噪声） | 提示用户重新录制 |
| `AUDIO_TOO_SHORT` | HTTP / WS | 音频时长 < 0.5 秒（PCM < 16000 bytes） | 提示用户延长录音 |
| `INVALID_FORMAT` | HTTP / WS | WAV 格式损坏 / JSON 格式非法 | 检查客户端音频采集代码 |
| `ASR_API_ERROR` | HTTP / WS | DashScope 上游服务异常（握手失败、超时、task-failed 等） | 等待后重试，持续失败检查 DashScope 账号状态 |
| `INTERNAL_ERROR` | HTTP / WS | 服务端未预期异常（配置错误、内存不足等） | 检查服务端日志，联系运维 |

---

## 5. 接口选型建议

| 场景 | 推荐接口 | 理由 |
|------|---------|------|
| 移动 App / 小程序 按住说话 | **HTTP POST** | 录完整段上传，实现简单，无需维护 WebSocket 状态 |
| Java 后端批量转写音频文件 | **HTTP POST** | 无状态，易于水平扩展 |
| 实时录音流式场景（如自动语音控制） | **WebSocket** | 可边录边发，减少感知延迟 |
| 多轮连续识别（如会议记录） | **WebSocket** | 一个连接多轮复用，减少建连开销 |

---

## 6. 完整调用示例

### 6.1 WebSocket 调用示例（Python）

```python
import asyncio
import json
import struct
import wave
import websockets


async def asr_websocket_demo(pcm_file: str, host: str = "localhost:20602"):
    """
    通过 WebSocket 接口进行语音识别。

    Args:
        pcm_file: 原始 PCM 文件路径（16kHz, mono, int16, little-endian）
        host: 服务地址
    """
    uri = f"ws://{host}/ws/asr"

    async with websockets.connect(uri) as ws:
        # 1. 发送 start
        await ws.send(json.dumps({
            "event": "start",
            "request_id": "demo-001",
            "language": "zh"
        }))

        # 2. 等待 started
        msg = json.loads(await ws.recv())
        assert msg["event"] == "started", f"期待 started，收到 {msg}"
        print(f"[WS] 任务已启动 request_id={msg.get('request_id')}")

        # 3. 发送 PCM 数据（每次 3200 bytes = 100ms）
        with open(pcm_file, "rb") as f:
            chunk_size = 3200
            total = 0
            while chunk := f.read(chunk_size):
                await ws.send(chunk)
                total += len(chunk)
        print(f"[WS] 已发送 {total} bytes 音频")

        # 4. 发送 stop
        await ws.send(json.dumps({"event": "stop"}))
        print("[WS] stop 已发送，等待识别结果...")

        # 5. 接收结果
        while True:
            raw = await ws.recv()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "result":
                print(f"[WS] 识别结果: {msg['text']}")

            elif event == "done":
                print(f"[WS] 任务完成: {msg['text']}")
                break

            elif event == "error":
                print(f"[WS] 错误 {msg['error_code']}: {msg['message']}")
                break


asyncio.run(asr_websocket_demo("test.pcm"))
```

### 6.2 WebSocket 调用示例（Java）

```java
import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Map;
import java.util.concurrent.CountDownLatch;

public class ASRWebSocketDemo {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final CountDownLatch latch = new CountDownLatch(1);

    public static void main(String[] args) throws Exception {
        WebSocketClient client = new WebSocketClient(
            new URI("ws://localhost:20602/ws/asr")
        ) {
            @Override
            public void onOpen(ServerHandshake handshake) {
                try {
                    // 1. 发送 start
                    send(JSON.writeValueAsString(Map.of(
                        "event", "start",
                        "request_id", "java-demo-001",
                        "language", "zh"
                    )));
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }

            @Override
            public void onMessage(String message) {
                try {
                    var msg = JSON.readValue(message, Map.class);
                    String event = (String) msg.get("event");

                    switch (event) {
                        case "started":
                            System.out.println("[WS] 任务已启动，发送音频...");
                            sendAudioAndStop();
                            break;
                        case "result":
                            System.out.println("[WS] 识别结果: " + msg.get("text"));
                            break;
                        case "done":
                            System.out.println("[WS] 任务完成: " + msg.get("text"));
                            latch.countDown();
                            break;
                        case "error":
                            System.err.println("[WS] 错误 " + msg.get("error_code")
                                + ": " + msg.get("message"));
                            latch.countDown();
                            break;
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }

            private void sendAudioAndStop() throws Exception {
                // 2. 发送 PCM 数据（每次 3200 bytes）
                byte[] pcm = Files.readAllBytes(Paths.get("test.pcm"));
                int chunkSize = 3200;
                for (int i = 0; i < pcm.length; i += chunkSize) {
                    int end = Math.min(i + chunkSize, pcm.length);
                    send(ByteBuffer.wrap(pcm, i, end - i));
                }

                // 3. 发送 stop
                send(JSON.writeValueAsString(Map.of("event", "stop")));
            }

            @Override
            public void onClose(int code, String reason, boolean remote) {
                System.out.println("[WS] 连接关闭: " + reason);
                latch.countDown();
            }

            @Override
            public void onError(Exception ex) {
                ex.printStackTrace();
                latch.countDown();
            }
        };

        client.connect();
        latch.await();
        client.close();
    }
}
```

### 6.3 WAV 文件格式转换参考

如果原始录音不是 16kHz 格式，需在发送前转换。以下为 Java 参考实现：

```java
import javax.sound.sampled.*;
import java.io.*;

/**
 * 将任意采样率的 PCM/WAV 重采样为 16kHz mono 16-bit
 */
public static byte[] resampleTo16kHz(byte[] inputWav) throws Exception {
    AudioInputStream in = AudioSystem.getAudioInputStream(
        new ByteArrayInputStream(inputWav)
    );

    AudioFormat targetFormat = new AudioFormat(
        16000,   // sampleRate
        16,      // sampleSizeInBits
        1,       // channels (mono)
        true,    // signed
        false    // littleEndian
    );

    AudioInputStream converted = AudioSystem.getAudioInputStream(targetFormat, in);

    ByteArrayOutputStream out = new ByteArrayOutputStream();
    // 封装为 WAV 输出（HTTP 接口需要 WAV；WebSocket 接口可以直接用 PCM bytes）
    AudioSystem.write(converted, AudioFileFormat.Type.WAVE, out);
    return out.toByteArray();
}
```

---

## 附录：服务端内部架构说明

> 此节供后端工程师排查问题使用，正常集成无需阅读。

### A. 底层 DashScope 调用协议

本服务内部通过 `infrastructure/api/asr_client.py` 调用 DashScope，使用 **OpenAI Realtime API 兼容格式**（非传统 DashScope NLS 格式）：

```
WebSocket 连接：
  wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime-2026-02-10
  Authorization: Bearer {DASHSCOPE_API_KEY}

事件流：
  服务端 → {"type":"session.created","session":{"input_audio_format":"pcm","sample_rate":16000,...}}
  客户端 → {"type":"input_audio_buffer.append","audio":"<base64 PCM>"}  （重复多次）
  客户端 → {"type":"input_audio_buffer.commit"}
  服务端 → {"type":"conversation.item.input_audio_transcription.completed","transcript":"..."}
```

### B. 关键限制

| 项目 | 限制 |
|------|------|
| WebSocket 接口转写延迟 | 约 1-3 秒（从发 `stop` 到收到 `done`），取决于音频长度和网络状况 |
| 最大音频长度 | 无硬限制，但建议单次不超过 60 秒，避免超时 |
| WebSocket 并发连接数 | 受 DashScope 账号 QPS 限制（默认 20 RPS） |
| HTTP 接口并发 | 受服务器线程/连接数限制，建议单机不超过 10 并发 |

### C. 服务端日志关键字

排查问题时可 `grep` 以下关键字：

```bash
# 查看所有 ASR 请求
grep "\[ASR\]" server.log

# 查看 DashScope 原始响应（调试用）
grep "\[ASR\]\[DashScope←\]" server.log

# 查看 WebSocket 连接
grep "\[ASR-WS\]" server.log

# 查看识别失败
grep "ASR.*失败\|ASR.*错误\|502" server.log
```
