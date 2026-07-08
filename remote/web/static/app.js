/**
 * app.js — 智能导览眼镜 Web 交互记录前端
 *
 * 功能：
 *   - 从 /api/interactions 获取 JSONL 数据
 *   - 渲染记录卡片（intro + qa）
 *   - 按事件类型筛选（全部 / intro / qa）
 *   - 每 5 秒自动刷新
 *   - 连接状态指示
 */

// ============================================================================
// 状态
// ============================================================================

const STATE = {
  filter: "all",        // "all" | "intro" | "qa"
  records: [],          // 当前展示的记录
  totalCount: 0,
  refreshTimer: null,
  REFRESH_INTERVAL: 5000,  // 5 秒
};

// ============================================================================
// DOM 引用
// ============================================================================

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
  recordsContainer: $("#records-container"),
  emptyState: $("#empty-state"),
  statusText: $("#status-text"),
  statusDot: $("#status-dot"),
  filterCount: $("#filter-count"),
  filterBtns: $$(".filter-btn"),
  refreshInfo: $("#refresh-info"),
  clock: $("#clock"),
  usbAudioStatus: $("#usb-audio-status"),
};

// ============================================================================
// API 请求
// ============================================================================

async function fetchInteractions(eventType, limit) {
  let url = "/api/interactions?limit=" + (limit || 50);
  if (eventType && eventType !== "all") {
    url += "&event_type=" + encodeURIComponent(eventType);
  }
  const resp = await fetch(url);
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  return resp.json();
}

async function fetchStatus() {
  const resp = await fetch("/api/status");
  if (!resp.ok) throw new Error("HTTP " + resp.status);
  return resp.json();
}

// ============================================================================
// 渲染
// ============================================================================

function renderRecords(records) {
  dom.recordsContainer.innerHTML = "";

  if (!records || records.length === 0) {
    dom.emptyState.style.display = "block";
    dom.recordsContainer.appendChild(dom.emptyState);
    return;
  }

  dom.emptyState.style.display = "none";

  records.forEach((r) => {
    const card = createRecordCard(r);
    dom.recordsContainer.appendChild(card);
  });
}

/** 渲染 USB Audio 设备状态 */
function renderUsbAudioStatus(statusData) {
  if (!dom.usbAudioStatus) return;
  const usb = statusData.usb_audio;
  if (!usb) {
    dom.usbAudioStatus.textContent = "—";
    dom.usbAudioStatus.className = "device-value";
    return;
  }
  if (usb.available) {
    dom.usbAudioStatus.textContent = "已识别";
    dom.usbAudioStatus.className = "device-value device-ok";
  } else {
    dom.usbAudioStatus.textContent = "未检测到";
    dom.usbAudioStatus.className = "device-value device-warn";
  }
}

function createRecordCard(r) {
  const card = document.createElement("div");
  card.className = "record-card";

  const isIntro = r.event_type === "intro";

  // ---- 头部行 ----
  const head = document.createElement("div");
  head.className = "card-head";

  const time = document.createElement("span");
  time.className = "card-time";
  time.textContent = r.timestamp || "";

  const badge = document.createElement("span");
  badge.className = "card-badge " + (isIntro ? "badge-intro" : "badge-qa");
  badge.textContent = isIntro ? "自动介绍" : "问答";

  const obj = document.createElement("span");
  obj.className = "card-object";
  obj.textContent = r.object_name || r.object_raw || "—";

  const conf = document.createElement("span");
  conf.className = "card-confidence";
  const c = r.confidence;
  conf.textContent = (c != null && c > 0) ? "置信度 " + (c * 100).toFixed(0) + "%" : "";

  head.appendChild(time);
  head.appendChild(badge);
  head.appendChild(obj);
  head.appendChild(conf);
  card.appendChild(head);

  // ---- 问答 ----
  if (!isIntro && r.user_question) {
    const qBlock = document.createElement("div");
    qBlock.className = "question-block";
    qBlock.innerHTML = '<div class="q-label">Q</div><div class="q-text">' + escHtml(r.user_question) + "</div>";
    card.appendChild(qBlock);
  }

  // ---- 回答 ----
  const aBlock = document.createElement("div");
  aBlock.className = "answer-block";
  const aLabel = isIntro ? "介绍" : "A";
  aBlock.innerHTML = '<div class="a-label">' + aLabel + "</div><div class=\"a-text\">" + escHtml(r.assistant_answer || "") + "</div>";
  card.appendChild(aBlock);

  // ---- 来源信息 ----
  const meta = document.createElement("div");
  meta.className = "card-meta";

  const source = document.createElement("span");
  source.className = "meta-source";
  source.textContent = "来源: " + (r.source || "—");
  meta.appendChild(source);

  const model = document.createElement("span");
  model.className = "meta-model";
  model.textContent = "模型: " + (r.model || "—");
  meta.appendChild(model);

  if (r.fps > 0) {
    const fps = document.createElement("span");
    fps.textContent = "FPS: " + r.fps.toFixed(1);
    meta.appendChild(fps);
  }

  card.appendChild(meta);

  return card;
}

/** HTML 转义 */
function escHtml(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ============================================================================
// 筛选
// ============================================================================

function setFilter(filter) {
  STATE.filter = filter;

  // 按钮状态
  dom.filterBtns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.filter === filter);
  });

  // 重新从服务器获取
  loadData();
}

// ============================================================================
// 数据加载
// ============================================================================

async function loadData() {
  try {
    // 并行获取交互记录和设备状态
    const [data, statusData] = await Promise.all([
      fetchInteractions(STATE.filter, 100),
      fetchStatus(),
    ]);
    STATE.records = data.records || [];
    STATE.totalCount = data.total || 0;

    renderRecords(STATE.records);
    renderUsbAudioStatus(statusData);
    dom.filterCount.textContent = "共 " + STATE.records.length + " 条";
    setStatus(true, "已连接 · " + STATE.totalCount + " 条记录");
  } catch (err) {
    console.error("loadData:", err);
    setStatus(false, "连接失败, 将在 " + (STATE.REFRESH_INTERVAL / 1000) + "s 后重试");
  }
}

// ============================================================================
// 状态指示
// ============================================================================

function setStatus(online, text) {
  dom.statusText.textContent = text || "";
  dom.statusDot.classList.toggle("online", online);
  dom.statusDot.classList.toggle("offline", !online);
}

// ============================================================================
// 自动刷新
// ============================================================================

function startAutoRefresh() {
  if (STATE.refreshTimer) clearInterval(STATE.refreshTimer);
  STATE.refreshTimer = setInterval(() => {
    loadData();
    updateClock();
  }, STATE.REFRESH_INTERVAL);
  dom.refreshInfo.textContent = "自动刷新: " + (STATE.REFRESH_INTERVAL / 1000) + "s";
}

function updateClock() {
  const now = new Date();
  dom.clock.textContent = now.toLocaleTimeString("zh-CN", { hour12: false });
}

// ============================================================================
// 初始化
// ============================================================================

function init() {
  // 筛选按钮事件
  dom.filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      setFilter(btn.dataset.filter);
    });
  });

  // 首次加载
  loadData();
  updateClock();
  startAutoRefresh();
}

// 页面就绪后启动
document.addEventListener("DOMContentLoaded", init);
