const state = { file: null, jobId: null, pollTimer: null, transcriptReady: false };
const $ = (id) => document.getElementById(id);

function setError(message) {
  const box = $("errorBox");
  box.textContent = message || "";
  box.classList.toggle("hidden", !message);
}
function setStatus(text) { $("statusText").textContent = text; }
function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function formatTimestamp(milliseconds, separator = ".") {
  const value = Math.max(0, Number(milliseconds) || 0);
  const hours = Math.floor(value / 3600000);
  const minutes = Math.floor((value % 3600000) / 60000);
  const seconds = Math.floor((value % 60000) / 1000);
  const millis = Math.floor(value % 1000);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}${separator}${String(millis).padStart(3, "0")}`;
}

function selectFile(file) {
  const allowed = [".aac", ".mp3", ".m4a", ".wav", ".mp4"];
  const extension = `.${file.name.split(".").pop().toLowerCase()}`;
  if (!allowed.includes(extension)) {
    setError("不支持的文件格式，请选择 aac、mp3、m4a、wav 或 mp4。");
    return;
  }
  setError("");
  state.file = file;
  $("fileName").textContent = file.name;
  $("fileSize").textContent = formatBytes(file.size);
  $("fileCard").classList.remove("hidden");
  $("startButton").disabled = false;
  setStatus("文件已就绪");
}

function clearFile() {
  state.file = null;
  state.jobId = null;
  $("fileInput").value = "";
  $("fileCard").classList.add("hidden");
  $("startButton").disabled = true;
  $("progressPanel").classList.add("hidden");
  setStatus("等待导入文件");
  resetTranscript();
}

function resetTranscript() {
  state.transcriptReady = false;
  $("transcriptList").innerHTML = "";
  $("transcriptList").classList.remove("timestamps-visible");
  $("transcriptEmpty").classList.remove("hidden");
  $("segmentCount").textContent = "0 句";
  $("toggleTimestamps").disabled = true;
  $("toggleTimestamps").textContent = "显示时间戳";
  $("toggleTimestamps").setAttribute("aria-pressed", "false");
  $("summaryButton").disabled = true;
  $("summaryLink").classList.add("hidden");
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = true; });
}

function renderProgress(job) {
  const active = ["transcribing", "summarizing"].includes(job.status);
  $("progressPanel").classList.toggle("hidden", !active && job.status !== "failed");
  $("progressValue").textContent = `${job.progress}%`;
  $("progressBar").style.width = `${job.progress}%`;
  $("progressLabel").textContent = job.status === "summarizing" ? "正在生成纪要" : "正在本地转写";
  if (job.status === "failed") {
    $("progressPanel").classList.remove("hidden");
    $("progressLabel").textContent = "任务失败";
    $("progressHint").textContent = job.error || "请检查配置后重试。";
  }
}

function renderTranscript(transcript) {
  const list = $("transcriptList");
  list.innerHTML = transcript.segments.map((segment, index) => `
    <article class="transcript-item">
      <div class="transcript-speaker">
        <span class="speaker-avatar">${escapeHtml(speakerMark(segment.speaker))}</span>
        <div class="transcript-speaker-info">
          <strong>${escapeHtml(segment.speaker)}</strong>
          <span class="speaker-turn">第 ${index + 1} 句</span>
          <span class="transcript-time">${escapeHtml(segment.start || formatTimestamp(segment.start_ms))}<br />↓ ${escapeHtml(segment.end || formatTimestamp(segment.end_ms))}</span>
        </div>
      </div>
      <p class="transcript-text">${escapeHtml(segment.text)}</p>
    </article>
  `).join("");
  $("transcriptEmpty").classList.toggle("hidden", transcript.segments.length > 0);
  $("segmentCount").textContent = transcript.segments.length + " 句";
  $("toggleTimestamps").disabled = transcript.segments.length === 0;
  state.transcriptReady = true;
  $("summaryButton").disabled = false;
  document.querySelectorAll(".export-button").forEach((button) => { button.disabled = false; });
}

function speakerMark(speaker) {
  const value = String(speaker || "Speaker").trim();
  const number = value.match(/^speaker\s*(\d+)$/i);
  if (number) return "S" + number[1];
  return Array.from(value.replace(/\s+/g, "")).slice(0, 2).join("") || "说话";
}

function toggleTimestamps() {
  const list = $("transcriptList");
  const visible = list.classList.toggle("timestamps-visible");
  $("toggleTimestamps").textContent = visible ? "隐藏时间戳" : "显示时间戳";
  $("toggleTimestamps").setAttribute("aria-pressed", String(visible));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

async function uploadAndStart() {
  if (!state.file) return;
  setError("");
  $("startButton").disabled = true;
  $("progressPanel").classList.remove("hidden");
  $("progressLabel").textContent = "正在上传";
  $("progressHint").textContent = "文件会写入当前项目的数据目录。";
  setStatus("上传中…");
  try {
    const form = new FormData();
    form.append("file", state.file);
    const uploaded = await request("/api/jobs", { method: "POST", body: form });
    state.jobId = uploaded.job_id;
    await request(`/api/jobs/${state.jobId}/transcribe`, { method: "POST" });
    setStatus("转写任务已启动");
    pollJob();
  } catch (error) {
    $("startButton").disabled = false;
    setStatus("启动失败");
    setError(error.message);
  }
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const job = await request(`/api/jobs/${state.jobId}`);
    renderProgress(job);
    if (job.status === "completed" && job.transcript_available) {
      const transcript = await request(`/api/jobs/${state.jobId}/transcript`);
      renderTranscript(transcript);
      setStatus(job.summary_available ? "转写与纪要已完成" : "转写完成");
      $("progressPanel").classList.add("hidden");
      return;
    }
    if (job.status === "failed") {
      setStatus("任务失败");
      setError(job.error || "任务失败，请查看终端日志。");
      $("startButton").disabled = false;
      return;
    }
    state.pollTimer = window.setTimeout(pollJob, 1000);
  } catch (error) {
    setError(error.message);
    state.pollTimer = window.setTimeout(pollJob, 2000);
  }
}

async function generateSummary() {
  if (!state.jobId || !state.transcriptReady) return;
  $("summaryButton").disabled = true;
  setError("");
  setStatus("纪要生成中…");
  try {
    await request(`/api/jobs/${state.jobId}/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: $("apiKey").value || null,
        base_url: $("baseUrl").value || null,
        model: $("model").value || null,
        extra_instruction: $("extraInstruction").value || "",
      }),
    });
    pollSummary();
  } catch (error) {
    $("summaryButton").disabled = false;
    setStatus("纪要启动失败");
    setError(error.message);
  }
}

async function pollSummary() {
  try {
    const job = await request(`/api/jobs/${state.jobId}`);
    renderProgress(job);
    if (job.status === "completed" && job.summary_available) {
      $("summaryLink").href = `/api/jobs/${state.jobId}/summary`;
      $("summaryLink").classList.remove("hidden");
      $("summaryButton").disabled = false;
      $("progressPanel").classList.add("hidden");
      setStatus("会议纪要已生成");
      return;
    }
    if (job.status === "failed") {
      $("summaryButton").disabled = false;
      setError(job.error || "纪要生成失败");
      setStatus("纪要生成失败");
      return;
    }
    window.setTimeout(pollSummary, 1000);
  } catch (error) {
    $("summaryButton").disabled = false;
    setError(error.message);
  }
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let body = null;
  try { body = await response.json(); } catch (_) { /* text/download responses are handled elsewhere */ }
  if (!response.ok) throw new Error(body?.detail || `请求失败（${response.status}）`);
  return body;
}

async function loadConfig() {
  try {
    const config = await request("/api/config");
    $("baseUrl").placeholder = config.llm_base_url;
    $("model").placeholder = config.llm_model;
  } catch (_) { /* optional UI hints */ }
}

$("chooseButton").addEventListener("click", () => $("fileInput").click());
$("fileInput").addEventListener("change", (event) => { if (event.target.files[0]) selectFile(event.target.files[0]); });
$("clearButton").addEventListener("click", clearFile);
$("startButton").addEventListener("click", uploadAndStart);
$("summaryButton").addEventListener("click", generateSummary);
$("toggleTimestamps").addEventListener("click", toggleTimestamps);
document.querySelectorAll(".export-button").forEach((button) => {
  button.addEventListener("click", () => {
    if (state.jobId) window.location.href = `/api/jobs/${state.jobId}/export/${button.dataset.format}`;
  });
});
$("dropzone").addEventListener("dragover", (event) => { event.preventDefault(); $("dropzone").classList.add("dragover"); });
$("dropzone").addEventListener("dragleave", () => $("dropzone").classList.remove("dragover"));
$("dropzone").addEventListener("drop", (event) => { event.preventDefault(); $("dropzone").classList.remove("dragover"); if (event.dataTransfer.files[0]) selectFile(event.dataTransfer.files[0]); });
$("dropzone").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") $("fileInput").click(); });
loadConfig();
