# Apple Silicon 支持

VoxNote 的 macOS arm64 发布环境固定为 Python 3.11、FunASR 1.4.16、PyTorch/torchaudio 2.6.0。独立锁文件从 PyPI 选择 macOS arm64 wheel，包含完整依赖版本与 SHA-256；不复用 Windows/Linux CPU 索引中的 `torch==2.6.0+cpu`。

## 安装与启动

先用原生 arm64 终端安装 Homebrew Python 和 ffmpeg。Rosetta 的 x86_64 终端/Python 不能使用这份 arm64 锁：

```bash
brew install python@3.11 ffmpeg
[ "$(uname -m)" = "arm64" ] || { echo "请打开原生 arm64 终端"; exit 1; }
python3.11 -c "import platform; assert platform.machine() == 'arm64', platform.machine()"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements-macos-arm64-py311.lock.txt
cp .env.example .env
```

想使用 Apple GPU 时，在 `.env` 中设置 `FUNASR_DEVICE=mps`。先验证 MPS 可用，再实际初始化全模型链并跑短 WAV：

```bash
python -c "import torch; print(torch.__version__, torch.backends.mps.is_available()); assert torch.backends.mps.is_available()"
python scripts/verify_funasr.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

转写使用 MPS 执行 ASR 主模型，VAD、标点和 CAM++ 说话人模型留在 CPU。这与 FunASR 1.4.16 的[子模型设备放置接口](https://github.com/modelscope/FunASR/blob/main/docs/python_api.md)一致。Docker 镜像仍按 CPU 运行；需要 MPS 时应在 macOS 原生 Python 环境启动应用。

MPS 不可用时应用会在加载模型前返回可操作的错误。遇到模型算子或内存问题时，可把 `.env` 中 `FUNASR_DEVICE` 改回 `cpu` 重试。MPS 性能和推理结果需要在目标 Mac 上实测；Windows 开发机只能验证 Apple Silicon 锁中的 wheel 可解析，不能替代 MPS 实机推理验收。

## 更新和交叉验收锁文件

需要 uv 0.7.14。该脚本重新解析 arm64/Python 3.11 依赖、写出哈希锁，并检查所有锁定包均有可用 wheel，不接受源码构建：

```bash
bash scripts/update_macos_lock.sh
```

当前维护机不是 Apple Silicon；已用 uv 针对 `aarch64-apple-darwin` 做过 `--no-build --require-hashes` dry-run。首次在 Apple Silicon 上发布前，仍需运行上方 PyTorch MPS 检查和 `scripts/verify_funasr.py`。
