# VoxNote

VoxNote 是一个跨平台的本地 Web 会议录音整理工具：浏览器负责操作，FastAPI 负责本地任务管理，FunASR 负责中文转写与说话人分段。原始音频、转写 JSON 和生成的 Markdown 纪要默认写入项目目录下的 `data/`，不会自动上传音频。

## 功能

- 拖拽或选择 `aac`、`mp3`、`m4a`、`wav`、`mp4`
- 默认模型链：`Paraformer-zh + FSMN-VAD + CT-Punc + CAM++`
- 逐句时间戳、说话人和文本 JSON
- 调用 DeepSeek 或其他 OpenAI 兼容的 `chat/completions` API 生成会议纪要
- 导出 Markdown、TXT、JSON、SRT
- Windows、macOS、Linux；第一版不包含实时录音、账号系统、云同步和安装包

## Python 直接启动

需要 Python 3.10+（建议 3.11）。项目默认使用 RTX/NVIDIA GPU；如果没有系统 ffmpeg，`imageio-ffmpeg` 会提供 Python 备用版本，用于把 aac/mp3/m4a/mp4 统一转换为 16 kHz 单声道 WAV。

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-gpu.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

若 PowerShell 禁止激活脚本，可以直接使用 `.\.venv\Scripts\python.exe -m pip ...` 和 `.\.venv\Scripts\python.exe -m uvicorn ...`。

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

ffmpeg 安装示例：

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y ffmpeg libsndfile1
```

Windows 可从 [ffmpeg.org](https://ffmpeg.org/download.html) 获取构建版本，解压后把 `bin` 加入 PATH；也可以把 `.env` 的 `FFMPEG_BINARY` 改成 ffmpeg 可执行文件的完整路径。

启动后打开 <http://127.0.0.1:8000>。

### GPU 与模型缓存

当前配置默认使用 `cuda:0`。模型缓存路径由 `.env` 中的 `MODELSCOPE_CACHE`、`HF_HOME`、`TORCH_HOME` 控制；如果项目位于 E 盘，可在本机 `.env` 中填写绝对路径，模型不会默认写入 C 盘用户目录。首次启动转写时会下载 Paraformer、FSMN-VAD、CT-Punc 和 CAM++ 模型。

Windows 用户需要把 `VOXNOTE_PYTHON` 指向已安装 CUDA PyTorch 的 Python 环境，然后运行：

```powershell
$env:VOXNOTE_PYTHON = 'C:\path\to\gpu\python.exe'
.\scripts\run_gpu.ps1
```

也可以把 `VOXNOTE_PYTHON=...` 写入本机 `.env`，之后直接运行脚本或双击 `scripts\run_gpu.bat`。手动启动使用：

```powershell
& $env:VOXNOTE_PYTHON -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

安装完成后，建议先运行一次模型自检：

```powershell
& $env:VOXNOTE_PYTHON scripts\verify_funasr.py
```

自检会初始化完整模型链并执行一个短 WAV 推理；成功时会输出 `"ok": true`。如果显存不足，可将 `FUNASR_DEVICE=cpu`，但 RTX 4070 建议保留 `cuda:0`。

## Docker

先准备配置：

```bash
cp .env.example .env
docker compose up --build
```

Windows PowerShell 可使用：

```powershell
Copy-Item .env.example .env
docker compose up --build
```

打开 <http://127.0.0.1:8000>。宿主机的 `data/` 保存原始音频与结果，`model-cache/` 保存模型缓存。第一次转写会下载模型，CPU 转写速度取决于音频长度和机器性能；有 NVIDIA GPU 的用户可以把 `FUNASR_DEVICE` 调整为对应设备并自行配置 GPU 版 PyTorch/Docker runtime。

Docker 会把容器内的 `/app/model-cache`、`/app/hf-cache` 和 `/app/torch-cache` 映射回项目目录，因此项目位于 E 盘时，模型仍保存在 E 盘。Docker 默认按 CPU 运行；本机 GPU 直连推荐使用上面的 `scripts\run_gpu.ps1`。

## 纪要 API

页面支持填写 API Key、Base URL 和模型名。Base URL 可以填写：

- DeepSeek：`https://api.deepseek.com`
- 其他 OpenAI 兼容服务：其 API 根地址或完整的 `/chat/completions` 地址

也可以在 `.env` 中设置 `DEEPSEEK_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。页面填写的 Key 仅随当前生成请求使用，不写入 `data/`。

## 验收模式与测试

FunASR 模型较大。只想先验证网页、任务轮询和四种导出格式时，可以把 `.env` 中的：

```dotenv
MOCK_TRANSCRIPTION=true
```

然后重启服务。该模式返回固定的示例中文片段，不下载模型；正式使用请恢复 `false`。运行测试：

```bash
python -m pytest
```

## 数据布局

每个任务位于 `data/jobs/<job_id>/`：

```text
original.<ext>       原始音频
job.json             任务状态
transcript.json      带时间戳、说话人、文字的结构化结果
summary.md           可选的 LLM 会议纪要
```

删除整个任务目录即可删除对应的本地数据。VoxNote 第一版不提供云端同步和自动清理。
