/**
 * GoodNotes WebAssembly Document Parser & Vector SVG Viewer
 * Powered by Pyodide (WASM Python)
 */

const I18N_DICT = {
  en: {
    pageTitle: "Document Parser for GoodNotes · Independent Vector SVG & PDF Viewer",
    headerTitle: "Document Parser for GoodNotes",
    headerSubtitle: "Independent Vector SVG, PDF & JSON Archive Inspector",
    statusLoading: "Loading WebAssembly Runtime...",
    statusReady: "WebAssembly Ready",
    statusError: "Runtime Error",
    dropzonePrimary: 'Drag & Drop <code>.goodnotes</code> file',
    dropzoneSecondary: 'or <span class="highlight">browse from device</span>',
    samplesTitle: "Quick Try Samples",
    sample1: "Example 1 (Handwritten Formulas & Images)",
    sample2: "Example 2 (Brush Styles & Stroke Variations)",
    sample3: "Example 3 (Multi-Layer Images & Chinese Text)",
    sample4: "Example 4 (Audio & Timed Inking Sync)",
    docInspectionTitle: "Document Inspection",
    audioTitle: "Audio & Timed Inking",
    audioSessionLabel: "Session:",
    audioSessionAll: "All Sessions (Continuous)",
    audioModeLabel: "Mode:",
    audioModeHighlight: "Highlight (Dim Future)",
    audioModeReveal: "Reveal (Hide Future)",
    audioModeNormal: "Full Display",
    audioAutoFlip: "Auto Flip",
    audioAutoFlipTitle: "Automatically flip page following audio",
    btnExportAudio: "Download Audio (.m4a)",
    btnExportHtml: "Export HTML Player",
    audioPlayerBtn: "Audio Recording",
    cliOptionsTitle: "CLI Parameters & Options",
    optParseAll: "Parse All Pages (-a)",
    optStickyNotes: "Sticky Notes (-s)",
    optStickyAuto: "Auto (Original)",
    optStickyOpen: "Force Open (Expanded)",
    optStickyClose: "Force Close (Collapsed)",
    optTextboxBorders: "Show Text Box Borders (-b)",
    optFillShapes: "Fill Vector Shapes (--fill)",
    statPages: "Pages",
    statCurPage: "Current Page",
    statStrokes: "Strokes",
    statDimensions: "Dimensions",
    btnExportPdf: "Export Multi-Page PDF",
    btnDownloadSvg: "Download Page SVG",
    btnExportJson: "Export JSON AST",
    privacyTitle: "100% Client-Side Privacy",
    privacyDesc: "Documents are decoded in-browser via WebAssembly. Nothing is ever sent to a server.",
    legalDisclaimer: '<strong>Disclaimer:</strong> This independent open-source project is not affiliated with, endorsed by, sponsored by, or officially connected to Goodnotes Limited. See <a href="https://github.com/Kaih1825/document-parser-for-goodnotes/blob/main/LEGAL-NOTICE.md" target="_blank" rel="noopener">LEGAL-NOTICE.md</a>.',
    btnFit: "Fit",
    emptyTitle: "No .goodnotes Document Loaded",
    emptyDesc: "Upload a user-supplied <code>.goodnotes</code> notebook or select a quick sample on the left to start inspecting.",
    footerText: 'This project is licensed under the MIT License; "Goodnotes" and related marks are trademarks of Goodnotes Limited, referenced solely for file format compatibility and parsing under nominative fair use without affiliation, endorsement, or sponsorship.',
    footerLegalNotice: "Legal Notice",
    footerContributing: "Contributing",
    tabTools: "Files & Tools",
    tabPreview: "Document Preview",
    
    // Dynamic text
    stepRead: "1. Read Archive",
    stepDecode: "2. Decode Protobuf",
    stepRender: "3. Render View",
    stepPrepare: "1. Prepare",
    stepRenderPages: "2. Render Pages",
    stepSavePdf: "3. Save PDF",
    
    openingDoc: "Opening .goodnotes Archive",
    readingBytes: (name, mb) => `Reading "${name}" (${mb} MB)...`,
    decodingWire: "Extracting Apple LZ4 streams and stroke ribbons...",
    renderingCanvas: (count) => `Parsed ${count} page(s). Rendering first page...`,
    readyLoaded: (count) => `Loaded ${count} page(s) successfully!`,
    toastLoaded: (name, count) => `✓ Loaded "${name}" (${count} pages)`,
    toastInvalidExt: (name) => `Invalid format "${name}". Only .goodnotes files are supported.`,
    exportingPdf: "Exporting Multi-Page PDF",
    pdfInit: (count) => `Initializing PDF builder for ${count} page(s)...`,
    pdfRenderingPage: (i, count, pct) => `Rendering page ${i} of ${count} (${pct}%)...`,
    pdfCompressing: (name) => `Compressing and saving "${name}"...`,
    toastPdfSuccess: (name, count) => `✓ Successfully exported "${name}" (${count} pages)`,
    toastSvgDownloaded: (name) => `✓ Downloaded ${name}`,
    toastJsonExported: (name) => `✓ Exported ${name}`,
    toastAudioExported: (name) => `✓ Downloaded audio "${name}"`,
    toastHtmlExported: (name) => `✓ Exported standalone player "${name}"`,
    toastJumpedTime: (t) => `⏱️ Seek to ${t}s`,
    engineInitializing: "WebAssembly engine is still initializing. Please wait...",
    noDocLoaded: "No document is currently loaded.",
  },
  zh_TW: {
    pageTitle: "Document Parser for GoodNotes · 獨立向量 SVG 與 PDF 檢視器",
    headerTitle: "Document Parser for GoodNotes",
    headerSubtitle: "獨立向量 SVG、PDF 與 JSON 封存檔解析檢視器",
    statusLoading: "正在載入 WebAssembly 引擎...",
    statusReady: "WebAssembly 引擎就緒",
    statusError: "執行環境錯誤",
    dropzonePrimary: '拖放 <code>.goodnotes</code> 檔案至此',
    dropzoneSecondary: '或 <span class="highlight">從本機選取檔案</span>',
    samplesTitle: "快速體驗範本",
    sample1: "範例 1 (手寫公式與插圖)",
    sample2: "範例 2 (多款筆刷與色彩筆跡)",
    sample3: "範例 3 (多層圖文疊加與中文手寫)",
    sample4: "範例 4 (語音錄音與時間筆跡同步)",
    docInspectionTitle: "文件解析資訊",
    audioTitle: "語音錄音與時間筆跡",
    audioSessionLabel: "錄音段落：",
    audioSessionAll: "全部連續播放 (All)",
    audioModeLabel: "同步模式：",
    audioModeHighlight: "同步點亮 (預先淡化)",
    audioModeReveal: "逐漸書寫 (隨錄音出現)",
    audioModeNormal: "完整顯示",
    audioAutoFlip: "自動翻頁",
    audioAutoFlipTitle: "播放時隨語音進度自動切換頁面",
    btnExportAudio: "下載錄音檔 (.m4a)",
    btnExportHtml: "匯出獨立網頁播放器",
    audioPlayerBtn: "語音錄音",
    cliOptionsTitle: "CLI 參數與轉譯設定",
    optParseAll: "解析所有頁面 (-a)",
    optStickyNotes: "便利貼展開狀態 (-s)",
    optStickyAuto: "自動 (原始狀態)",
    optStickyOpen: "強制展開 (Open)",
    optStickyClose: "強制收合 (Close)",
    optTextboxBorders: "顯示文字方塊外框 (-b)",
    optFillShapes: "封閉向量圖形填色 (--fill)",
    statPages: "總頁數",
    statCurPage: "目前頁面",
    statStrokes: "筆畫數",
    statDimensions: "頁面尺寸",
    btnExportPdf: "匯出多頁向量 PDF",
    btnDownloadSvg: "下載本頁向量 SVG",
    btnExportJson: "匯出 JSON 語法樹",
    privacyTitle: "100% 本地瀏覽器隱私保護",
    privacyDesc: "所有文件皆由 WebAssembly 於瀏覽器本地解碼，絕不上傳任何伺服器。",
    legalDisclaimer: '<strong>免責聲明：</strong>本獨立開源專案與 Goodnotes Limited 無任何隸屬、贊助或官方合作關係。詳見 <a href="https://github.com/Kaih1825/document-parser-for-goodnotes/blob/main/LEGAL-NOTICE.md" target="_blank" rel="noopener">LEGAL-NOTICE.md</a>。',
    btnFit: "重設比例",
    emptyTitle: "尚未載入任何 .goodnotes 文件",
    emptyDesc: "請上傳您的 <code>.goodnotes</code> 筆記檔，或由左側選取範例檔案開始檢視。",
    footerText: '本專案採 MIT 授權；「Goodnotes」及其相關名稱與標誌皆為 Goodnotes Limited 之商標，本專案引用僅為檔案格式相容性與解析之指示性合理使用，無任何官方隸屬、背書或贊助關係。',
    footerLegalNotice: "法律聲明",
    footerContributing: "貢獻指南",
    tabTools: "檔案與工具",
    tabPreview: "文件預覽",
    
    // Dynamic text
    stepRead: "1. 讀取封存檔",
    stepDecode: "2. 解碼 Protobuf",
    stepRender: "3. 向量畫布繪製",
    stepPrepare: "1. 初始化",
    stepRenderPages: "2. 逐頁向量轉譯",
    stepSavePdf: "3. 儲存 PDF",
    
    openingDoc: "正在讀取 .goodnotes 筆記",
    readingBytes: (name, mb) => `正在讀取 "${name}" (${mb} MB)...`,
    decodingWire: "正在解碼 Apple LZ4 串流與筆跡幾何座標...",
    renderingCanvas: (count) => `已解析 ${count} 頁。正在繪製第一頁...`,
    readyLoaded: (count) => `成功載入 ${count} 個頁面！`,
    toastLoaded: (name, count) => `✓ 成功載入 "${name}"（共 ${count} 頁）`,
    toastInvalidExt: (name) => `檔案格式錯誤「${name}」，本工具僅支援 .goodnotes 檔案。`,
    exportingPdf: "正在匯出多頁向量 PDF",
    pdfInit: (count) => `正在初始化 ${count} 頁的向量 PDF 生成器...`,
    pdfRenderingPage: (i, count, pct) => `正在轉譯第 ${i} 頁 / 共 ${count} 頁 (${pct}%)...`,
    pdfCompressing: (name) => `正在封裝並儲存 "${name}"...`,
    toastPdfSuccess: (name, count) => `✓ 成功匯出 "${name}"（共 ${count} 頁純向量 PDF）`,
    toastSvgDownloaded: (name) => `✓ 已下載 ${name}`,
    toastJsonExported: (name) => `✓ 已匯出 ${name}`,
    toastAudioExported: (name) => `✓ 已下載錄音音訊檔 "${name}"`,
    toastHtmlExported: (name) => `✓ 已匯出獨立 HTML 播放器 "${name}"`,
    toastJumpedTime: (t) => `⏱️ 已跳轉至 ${t} 秒`,
    engineInitializing: "WebAssembly 引擎仍在初始化中，請稍候...",
    noDocLoaded: "目前尚未載入任何文件。",
  }
};

// Application State
const state = {
  lang: "en",
  pyodide: null,
  isReady: false,
  currentDocBytes: null,
  currentDocName: "",
  pageCount: 0,
  currentPageIndex: 0,
  currentDocMeta: null,
  currentSvgString: "",
  isPageRendering: false,
  pageSvgCache: new Map(), // key -> { svg, strokes_count, width, height }
  zoomLevel: 1.0,
  userHasZoomed: false,
  activeMobileTab: "sidebar",
  cliOptions: {
    parseAll: true,
    stickyNoteState: "auto",
    textboxState: false,
    fillShapes: true,
  },
  audio: {
    recordings: [],
    currentSessionIndex: -1, // -1 = All Continuous, >= 0 = Single session
    audioEl: new Audio(),
    isPlaying: false,
    speedLevels: [0.75, 1.0, 1.25, 1.5, 2.0],
    speedIndex: 1,
    autoFlip: true,
    mode: "highlight", // highlight, reveal, normal
    animFrameId: null,
    totalDuration: 0,
    recOffsets: [], // session start timestamps
    strokeMap: new Map(), // stroke_uuid -> { sessionIndex, timestamp, page_uuid }
  },
};

// DOM Elements
const el = {
  langPillSwitch: document.getElementById("lang-pill-switch"),
  langBtnEn: document.getElementById("lang-btn-en"),
  langBtnZh: document.getElementById("lang-btn-zh"),
  mobileNavTabs: document.getElementById("mobile-view-tabs"),
  tabBtnSidebar: document.getElementById("tab-btn-sidebar"),
  tabBtnPreview: document.getElementById("tab-btn-preview"),
  workspace: document.querySelector(".workspace"),
  runtimeStatus: document.getElementById("runtime-status"),
  statusText: document.querySelector("#runtime-status .status-text"),
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("file-input"),
  optParseAll: document.getElementById("opt-parse-all"),
  optStickyNotes: document.getElementById("opt-sticky-notes"),
  optTextboxBorders: document.getElementById("opt-textbox-borders"),
  optFillShapes: document.getElementById("opt-fill-shapes"),
  audioPlayerCard: document.getElementById("audio-player-card"),
  audioBadgeCount: document.getElementById("audio-badge-count"),
  audioSessionSelectContainer: document.getElementById("audio-session-select-container"),
  audioSessionSelect: document.getElementById("audio-session-select"),
  audioModeSelect: document.getElementById("audio-mode-select"),
  audioScrubber: document.getElementById("audio-scrubber"),
  audioProgressBar: document.getElementById("audio-progress-bar"),
  audioCurrentTime: document.getElementById("audio-current-time"),
  audioDuration: document.getElementById("audio-duration"),
  btnAudioRewind: document.getElementById("btn-audio-rewind"),
  btnAudioPlay: document.getElementById("btn-audio-play"),
  btnAudioForward: document.getElementById("btn-audio-forward"),
  iconAudioPlay: document.getElementById("icon-audio-play"),
  iconAudioPause: document.getElementById("icon-audio-pause"),
  btnAudioSpeed: document.getElementById("btn-audio-speed"),
  btnAudioAutoFlip: document.getElementById("btn-audio-auto-flip"),
  btnDownloadAudio: document.getElementById("btn-download-audio"),
  btnDownloadHtml: document.getElementById("btn-download-html"),
  btnDownloadAudioMain: document.getElementById("btn-download-audio-main"),
  btnDownloadHtmlMain: document.getElementById("btn-download-html-main"),
  btnToolbarAudio: document.getElementById("btn-toolbar-audio"),
  toolbarAudioBadge: document.getElementById("toolbar-audio-badge"),
  canvasAudioBar: document.getElementById("canvas-audio-bar"),
  cabBtnRewind: document.getElementById("cab-btn-rewind"),
  cabBtnPlay: document.getElementById("cab-btn-play"),
  cabBtnForward: document.getElementById("cab-btn-forward"),
  cabIconPlay: document.getElementById("cab-icon-play"),
  cabIconPause: document.getElementById("cab-icon-pause"),
  cabCurrentTime: document.getElementById("cab-current-time"),
  cabDuration: document.getElementById("cab-duration"),
  cabScrubber: document.getElementById("cab-scrubber"),
  cabProgressBar: document.getElementById("cab-progress-bar"),
  cabSessionSelect: document.getElementById("cab-session-select"),
  cabModeSelect: document.getElementById("cab-mode-select"),
  cabBtnSpeed: document.getElementById("cab-btn-speed"),
  cabBtnAutoFlip: document.getElementById("cab-btn-auto-flip"),
  cabBtnDownloadAudio: document.getElementById("cab-btn-download-audio"),
  cabBtnDownloadHtml: document.getElementById("cab-btn-download-html"),
  docStatsCard: document.getElementById("doc-stats-card"),
  statPages: document.getElementById("stat-pages"),
  statCurPage: document.getElementById("stat-cur-page"),
  statStrokes: document.getElementById("stat-strokes"),
  statDimensions: document.getElementById("stat-dimensions"),
  btnDownloadPdf: document.getElementById("btn-download-pdf"),
  btnDownloadSvg: document.getElementById("btn-download-svg"),
  btnDownloadJson: document.getElementById("btn-download-json"),
  btnPrevPage: document.getElementById("btn-prev-page"),
  btnNextPage: document.getElementById("btn-next-page"),
  pageIndicator: document.getElementById("page-indicator"),
  btnZoomIn: document.getElementById("btn-zoom-in"),
  btnZoomOut: document.getElementById("btn-zoom-out"),
  btnZoomReset: document.getElementById("btn-zoom-reset"),
  zoomLevelText: document.getElementById("zoom-level"),
  emptyState: document.getElementById("empty-state"),
  loadingOverlay: document.getElementById("loading-spinner"),
  loadingMsg: document.getElementById("loading-msg"),
  progressTitle: document.getElementById("progress-title"),
  progressPercent: document.getElementById("progress-percent"),
  progressBarFill: document.getElementById("progress-bar-fill"),
  step1: document.getElementById("step-1"),
  step2: document.getElementById("step-2"),
  step3: document.getElementById("step-3"),
  toastContainer: document.getElementById("toast-container"),
  canvasContainer: document.getElementById("canvas-container"),
  svgStage: document.getElementById("svg-stage"),
  sampleButtons: document.querySelectorAll(".btn-sample"),
};

function t(key, ...args) {
  const dict = I18N_DICT[state.lang] || I18N_DICT.en;
  const item = dict[key] !== undefined ? dict[key] : (I18N_DICT.en[key] || key);
  if (typeof item === "function") {
    return item(...args);
  }
  return item;
}

function detectLanguage() {
  const urlParams = new URLSearchParams(window.location.search);
  const langParam = urlParams.get("lang");
  const hash = window.location.hash.replace(/^#/, "");

  if (langParam === "zh_TW" || langParam === "zh-TW" || langParam === "zh" || hash === "zh_TW" || hash === "zh-TW") {
    return "zh_TW";
  }
  if (langParam === "en" || hash === "en") {
    return "en";
  }

  const saved = localStorage.getItem("gn_parser_lang");
  if (saved === "zh_TW" || saved === "en") return saved;

  const browserLang = navigator.language || navigator.userLanguage || "";
  if (browserLang.startsWith("zh")) {
    return "zh_TW";
  }
  return "en";
}

function setLanguage(lang, updateUrl = true) {
  state.lang = (lang === "zh_TW" || lang === "zh-TW" || lang === "zh") ? "zh_TW" : "en";
  try {
    localStorage.setItem("gn_parser_lang", state.lang);
  } catch (e) {}

  if (updateUrl) {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", state.lang);
    window.history.replaceState(null, "", url.toString());
  }

  if (el.langPillSwitch) {
    el.langPillSwitch.setAttribute("data-active", state.lang);
  }

  if (el.langBtnEn && el.langBtnZh) {
    el.langBtnEn.classList.toggle("active", state.lang === "en");
    el.langBtnEn.setAttribute("aria-selected", state.lang === "en" ? "true" : "false");
    el.langBtnZh.classList.toggle("active", state.lang === "zh_TW");
    el.langBtnZh.setAttribute("aria-selected", state.lang === "zh_TW" ? "true" : "false");
  }

  const dict = I18N_DICT[state.lang];
  document.title = dict.pageTitle;

  document.querySelectorAll("[data-i18n]").forEach((elem) => {
    const key = elem.getAttribute("data-i18n");
    if (dict[key] !== undefined) {
      elem.innerHTML = dict[key];
    }
  });

  if (state.isReady) {
    updateStatus("ready", dict.statusReady);
  }
}

/**
 * Switch Mobile View Tab (Sidebar vs Preview)
 */
function switchMobileTab(tabName) {
  state.activeMobileTab = tabName === "preview" ? "preview" : "sidebar";
  if (el.workspace) {
    el.workspace.setAttribute("data-active-tab", state.activeMobileTab);
  }
  if (el.tabBtnSidebar && el.tabBtnPreview) {
    el.tabBtnSidebar.classList.toggle("active", state.activeMobileTab === "sidebar");
    el.tabBtnSidebar.setAttribute("aria-selected", state.activeMobileTab === "sidebar" ? "true" : "false");
    el.tabBtnPreview.classList.toggle("active", state.activeMobileTab === "preview");
    el.tabBtnPreview.setAttribute("aria-selected", state.activeMobileTab === "preview" ? "true" : "false");
  }
  if (state.activeMobileTab === "preview") {
    setTimeout(fitToScreen, 60);
  }
}

/**
 * Yield control back to browser event loop to allow UI rendering and smooth 60fps animations
 */
function yieldThread(ms = 16) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Show Toast Notification
 */
function showToast(message, type = "success", duration = 3500) {
  if (!el.toastContainer) return;

  const toast = document.createElement("div");
  toast.className = `toast-item ${type}`;

  const icon = type === "success" ? "✓" : type === "error" ? "✗" : "ℹ";
  toast.innerHTML = `<span style="font-weight: 700;">${icon}</span><span>${message}</span>`;

  el.toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("fade-out");
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Update Progress Modal with animated progress bar and steps
 */
function updateProgress({ title = "Processing Document", detail = "", percent = 0, activeStep = 1, stepLabels = null }) {
  if (el.progressTitle && title) el.progressTitle.textContent = title;
  if (el.loadingMsg && detail) el.loadingMsg.textContent = detail;
  if (el.progressPercent) el.progressPercent.textContent = `${Math.min(100, Math.max(0, Math.round(percent)))}%`;
  if (el.progressBarFill) el.progressBarFill.style.width = `${Math.min(100, Math.max(0, percent))}%`;

  if (stepLabels && stepLabels.length === 3) {
    if (el.step1) el.step1.textContent = stepLabels[0];
    if (el.step2) el.step2.textContent = stepLabels[1];
    if (el.step3) el.step3.textContent = stepLabels[2];
  }

  [el.step1, el.step2, el.step3].forEach((stepEl, idx) => {
    if (!stepEl) return;
    const stepNum = idx + 1;
    stepEl.className = "step-badge";
    if (stepNum < activeStep) {
      stepEl.classList.add("completed");
    } else if (stepNum === activeStep) {
      stepEl.classList.add("active");
    }
  });

  el.loadingOverlay.classList.remove("hidden");
}

function hideProgress() {
  if (el.loadingOverlay) {
    el.loadingOverlay.classList.add("hidden");
  }
}

/**
 * Asynchronously fetch parser package wheel buffer with fallback candidates
 */
async function fetchPackageWheelBuffer() {
  const wheelCandidates = [
    "./goodnotes_document_parser-0.1.0-py3-none-any.whl",
    "../dist/goodnotes_document_parser-0.1.0-py3-none-any.whl",
    "./dist/goodnotes_document_parser-0.1.0-py3-none-any.whl",
  ];

  for (const wheelUrl of wheelCandidates) {
    try {
      const resp = await fetch(wheelUrl);
      if (resp.ok) {
        return await resp.arrayBuffer();
      }
    } catch (e) {
      console.warn(`[Parser] Fetch ${wheelUrl} failed:`, e);
    }
  }
  throw new Error("Could not find or load goodnotes_document_parser wheel package.");
}

/**
 * Initialize Pyodide Runtime & Python Parser Package concurrently
 */
async function initPyodideRuntime() {
  try {
    updateStatus("loading", t("statusLoading"));
    
    // Concurrently download Pyodide WASM runtime and parser wheel
    const wheelPromise = fetchPackageWheelBuffer();
    const pyodidePromise = loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/",
    });

    const [pyodideInstance, wheelBuffer] = await Promise.all([pyodidePromise, wheelPromise]);
    state.pyodide = pyodideInstance;

    updateStatus("loading", "Loading Parser Engine...");

    await state.pyodide.unpackArchive(wheelBuffer, "whl");

    // Define Python bridge helpers
    await state.pyodide.runPythonAsync(`
import io
import json
import tempfile
from pathlib import Path
from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import page_to_svg, write_svg

current_doc = None
current_pages = []

def load_document_bytes(data_bytes, filename="doc.goodnotes", parse_all=False):
    global current_doc, current_pages
    raw_bytes = bytes(data_bytes)
    if hasattr(GoodNotesDocument, "from_bytes"):
        current_doc = GoodNotesDocument.from_bytes(raw_bytes, filename=filename)
    else:
        try:
            current_doc = GoodNotesDocument.open(raw_bytes)
        except Exception:
            import zipfile
            current_doc = GoodNotesDocument(Path(filename), zipfile.ZipFile(io.BytesIO(raw_bytes)))
    
    try:
        current_pages = current_doc.pages(parse_all=bool(parse_all))
    except Exception:
        current_pages = current_doc.pages()
    
    return {
        "page_count": len(current_pages),
        "filename": filename,
        "page_uuids": [p.uuid for p in current_pages],
    }

def reload_pages(parse_all=True):
    global current_doc, current_pages
    if not current_doc:
        return 0
    try:
        current_pages = current_doc.pages(parse_all=bool(parse_all))
    except Exception:
        current_pages = current_doc.pages()
    return len(current_pages)

def get_page_svg(page_idx):
    global current_doc, current_pages
    if not current_doc or not current_pages or page_idx < 0 or page_idx >= len(current_pages):
        return ""
    return page_to_svg(current_pages[page_idx], current_doc, fill_shapes=True, stroke_data_attributes=True)

def get_page_stats(page_idx):
    global current_pages
    if not current_pages or page_idx < 0 or page_idx >= len(current_pages):
        return {}
    p = current_pages[page_idx]
    return {
        "index": p.index,
        "uuid": p.uuid,
        "width": p.dimensions.width,
        "height": p.dimensions.height,
        "strokes_count": len(p.strokes),
        "shapes_count": len(p.shapes),
        "text_count": len(p.text_elements),
        "images_count": len(p.image_elements),
    }

def get_page_bundle(page_idx, sticky_note_state='auto', textbox_state=False, fill_shapes=True):
    global current_doc, current_pages
    if not current_doc or not current_pages or page_idx < 0 or page_idx >= len(current_pages):
        return {}
    p = current_pages[page_idx]
    svg_str = page_to_svg(
        p,
        current_doc,
        fill_shapes=bool(fill_shapes),
        sticky_note_state=str(sticky_note_state),
        textbox_state=bool(textbox_state),
        stroke_data_attributes=True
    )
    return {
        "index": p.index,
        "uuid": p.uuid,
        "width": p.dimensions.width,
        "height": p.dimensions.height,
        "strokes_count": len(p.strokes),
        "shapes_count": len(p.shapes),
        "text_count": len(p.text_elements),
        "images_count": len(p.image_elements),
        "svg": svg_str,
    }

def export_json_ast():
    global current_doc
    if not current_doc:
        return "{}"
    return json.dumps(current_doc.as_json(), ensure_ascii=False, indent=2)

def get_document_recordings():
    global current_doc, current_pages
    if not current_doc:
        return "[]"
    try:
        recs = current_doc.recordings()
        pages = current_pages if current_pages else current_doc.pages()

        def match_page_uuid(page_uuid_str):
            if not page_uuid_str:
                return None
            clean = page_uuid_str.replace("-", "").lower()
            for idx, p in enumerate(pages):
                p_clean = p.uuid.replace("-", "").lower()
                if p_clean == clean or (len(p_clean) >= 28 and len(clean) >= 28 and p_clean[:28] == clean[:28]):
                    return idx
            return None

        out = []
        import base64
        for r in recs:
            d = r.as_dict()
            audio_b64 = ""
            if r.audio_attachment_path:
                try:
                    audio_bytes = current_doc.read(r.audio_attachment_path)
                    audio_b64 = base64.b64encode(audio_bytes).decode('ascii')
                except Exception as ex:
                    print("read audio error:", ex)
            d["audio_base64"] = audio_b64

            # Pre-resolve exact document page_index for every stroke (-1 if deleted/unmapped)
            if "stroke_timings" in d:
                for st in d["stroke_timings"]:
                    matched_idx = match_page_uuid(st.get("page_uuid", ""))
                    st["page_index"] = matched_idx if matched_idx is not None else -1

            out.append(d)
        return json.dumps(out)
    except Exception as e:
        print("[Parser] Recordings extraction error:", e)
        import traceback
        traceback.print_exc()
        return "[]"

def get_recording_audio_bytes(rec_idx=0):
    global current_doc
    if not current_doc:
        return b""
    recs = current_doc.recordings()
    if 0 <= rec_idx < len(recs) and recs[rec_idx].audio_attachment_path:
        return current_doc.read(recs[rec_idx].audio_attachment_path)
    return b""

def export_recording_html(sticky_note_state='auto', textbox_state=False, fill_shapes=True, parse_all=True):
    global current_doc
    if not current_doc:
        return ""
    from goodnotes_re.export import write_recording_html
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp_path = f.name
    try:
        write_recording_html(
            current_doc,
            tmp_path,
            parse_all=bool(parse_all),
            sticky_note_state=str(sticky_note_state),
            textbox_state=bool(textbox_state),
            fill_shapes=bool(fill_shapes)
        )
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    finally:
        Path(tmp_path).unlink(missing_ok=True)
`);

    state.isReady = true;
    updateStatus("ready", "WebAssembly Ready");
    console.log("[Parser] GoodNotes WebAssembly parser initialized successfully.");
  } catch (error) {
    console.error("[Parser] Initialization failed:", error);
    updateStatus("error", "Runtime Error");
    alert("Failed to initialize WebAssembly Python runtime: " + error.message);
  }
}

/**
 * Update Header Status UI
 */
function updateStatus(type, message) {
  el.runtimeStatus.className = `status-indicator ${type}`;
  el.statusText.textContent = message;
}

/**
 * Show / Hide Global Loading Overlay
 */
function showLoading(message = "Parsing document...") {
  el.loadingMsg.textContent = message;
  el.loadingOverlay.classList.remove("hidden");
}

function hideLoading() {
  el.loadingOverlay.classList.add("hidden");
}

function isGoodNotesFile(filename) {
  return typeof filename === "string" && filename.trim().toLowerCase().endsWith(".goodnotes");
}

/**
 * Parse and load GoodNotes binary ArrayBuffer into Pyodide
 */
async function processGoodNotesBuffer(arrayBuffer, filename) {
  if (!state.isReady) {
    showToast("WebAssembly engine is still initializing. Please wait...", "info");
    return;
  }

  if (!isGoodNotesFile(filename)) {
    showToast(`Invalid format for "${filename}". Only .goodnotes files are supported.`, "error", 5000);
    return;
  }

  const mbSize = (arrayBuffer.byteLength / 1024 / 1024).toFixed(2);
  updateProgress({
    title: "Opening .goodnotes Archive",
    detail: `Reading "${filename}" (${mbSize} MB)...`,
    percent: 15,
    activeStep: 1,
    stepLabels: ["1. Read Archive", "2. Decode Protobuf", "3. Render View"],
  });
  await yieldThread(40);

  try {
    pdfDocCache.clear();
    pdfPageImageCache.clear();
    state.currentDocBytes = new Uint8Array(arrayBuffer);
    state.currentDocName = filename;

    updateProgress({
      title: "Decoding Protobuf Wire Streams",
      detail: "Extracting Apple LZ4 streams and stroke ribbons...",
      percent: 45,
      activeStep: 2,
    });
    await yieldThread(40);

    // Send bytes to Python runtime
    const loadFn = state.pyodide.globals.get("load_document_bytes");
    const resultProxy = loadFn(state.currentDocBytes, filename, state.cliOptions.parseAll);
    const docInfo = resultProxy.toJs();
    resultProxy.destroy();

    state.pageCount = docInfo.get("page_count") || 1;
    state.currentPageIndex = 0;
    state.userHasZoomed = false;
    state.pageSvgCache.clear();

    // Store page UUIDs array
    state.pageUuids = [];
    const rawPageUuids = docInfo.get("page_uuids");
    if (rawPageUuids) {
      const pUuids = rawPageUuids.toJs ? rawPageUuids.toJs() : rawPageUuids;
      if (Array.isArray(pUuids)) {
        state.pageUuids = pUuids;
      }
    }

    // Extract Audio Recordings & Timeline data
    let recordings = [];
    try {
      const getRecsFn = state.pyodide.globals.get("get_document_recordings");
      if (getRecsFn) {
        const jsonStr = getRecsFn();
        recordings = JSON.parse(jsonStr || "[]");
        console.log(`[Parser] Extracted ${recordings.length} recording session(s)`);
      }
    } catch (recErr) {
      console.warn("[Parser] Audio recordings query skipped:", recErr);
    }

    if (Array.isArray(recordings) && recordings.length > 0) {
      initAudioPlayer(recordings);
    } else {
      resetAudioPlayer();
    }

    updateProgress({
      title: "Rendering Vector Canvas",
      detail: `Parsed ${state.pageCount} page(s). Rendering first page...`,
      percent: 80,
      activeStep: 3,
    });
    await yieldThread(30);

    // Render first page
    await renderCurrentPage(false);

    // Show stats card & hide empty state
    el.emptyState.classList.add("hidden");
    el.svgStage.classList.remove("hidden");
    el.docStatsCard.classList.remove("hidden");

    // Automatically switch to Preview tab on mobile/tablets when document is loaded
    if (window.innerWidth <= 860) {
      switchMobileTab("preview");
    }

    updateProgress({
      title: "Ready",
      detail: `Loaded ${state.pageCount} page(s) successfully!`,
      percent: 100,
      activeStep: 3,
    });
    await yieldThread(180);

    showToast(`✓ Loaded "${filename}" (${state.pageCount} pages)`, "success");
  } catch (err) {
    console.error("[Parser] Document parsing failed:", err);
    showToast("Parsing failed: " + err.message, "error", 5000);
    alert("Error parsing .goodnotes document:\n" + err.message);
  } finally {
    hideProgress();
  }
}

// Global Caches for High-Performance Rendering
const pdfDocCache = new Map();
const pdfPageImageCache = new Map();

/**
 * Render the current page SVG
 */
async function renderCurrentPage(showModal = true) {
  if (state.isPageRendering) return;
  state.isPageRendering = true;

  const optKey = `${state.currentPageIndex}_${state.cliOptions.stickyNoteState}_${state.cliOptions.textboxState}_${state.cliOptions.fillShapes}`;

  // Instant render from cache if already processed
  if (state.pageSvgCache.has(optKey)) {
    try {
      const cached = state.pageSvgCache.get(optKey);
      el.svgStage.innerHTML = cached.svg;
      state.currentSvgString = cached.svg;

      // Update synchronized stroke states
      updateAudioSync();

      // Update Stats UI
      el.statPages.textContent = `${state.pageCount}`;
      el.statCurPage.textContent = `${state.currentPageIndex + 1}`;
      el.statStrokes.textContent = `${cached.strokes_count || 0}`;
      el.statDimensions.textContent = `${Math.round(cached.width || 0)} × ${Math.round(cached.height || 0)} pt`;

      // Update Pagination Toolbar
      el.pageIndicator.textContent = `Page ${state.currentPageIndex + 1} / ${state.pageCount}`;
      el.btnPrevPage.disabled = state.currentPageIndex <= 0;
      el.btnNextPage.disabled = state.currentPageIndex >= state.pageCount - 1;

      if (!state.userHasZoomed) {
        fitToScreen();
      } else {
        applyZoom();
      }
    } finally {
      state.isPageRendering = false;
    }
    return;
  }

  if (showModal) {
    updateProgress({
      title: `Rendering Page ${state.currentPageIndex + 1}`,
      detail: "Building vector strokes and PDF template background...",
      percent: 50,
      activeStep: 3,
      stepLabels: ["1. Read Archive", "2. Decode Protobuf", "3. Render View"],
    });
    await yieldThread(10);
  }

  try {
    const getBundleFn = state.pyodide.globals.get("get_page_bundle");
    const bundleProxy = getBundleFn(
      state.currentPageIndex,
      state.cliOptions.stickyNoteState,
      state.cliOptions.textboxState,
      state.cliOptions.fillShapes
    );
    const bundle = bundleProxy.toJs();
    bundleProxy.destroy();

    state.currentSvgString = bundle.get("svg") || "";

    // Inject SVG into DOM
    el.svgStage.innerHTML = state.currentSvgString;

    // Resolve any PDF background / sticker placeholders using PDF.js
    await resolvePdfPlaceholders(el.svgStage);
    state.currentSvgString = el.svgStage.innerHTML;

    const strokesCount = bundle.get("strokes_count") || 0;
    const w = bundle.get("width") || 0;
    const h = bundle.get("height") || 0;

    // Save to instant page cache
    state.pageSvgCache.set(optKey, {
      svg: state.currentSvgString,
      strokes_count: strokesCount,
      width: w,
      height: h,
    });

    // Update synchronized stroke states for audio playback
    updateAudioSync();

    // Update Stats UI
    el.statPages.textContent = `${state.pageCount}`;
    el.statCurPage.textContent = `${state.currentPageIndex + 1}`;
    el.statStrokes.textContent = `${strokesCount}`;
    el.statDimensions.textContent = `${Math.round(w)} × ${Math.round(h)} pt`;

    // Update Pagination Toolbar
    el.pageIndicator.textContent = `Page ${state.currentPageIndex + 1} / ${state.pageCount}`;
    el.btnPrevPage.disabled = state.currentPageIndex <= 0;
    el.btnNextPage.disabled = state.currentPageIndex >= state.pageCount - 1;

    // Apply auto-fit zoom transformation if user hasn't manually zoomed
    if (!state.userHasZoomed) {
      fitToScreen();
    } else {
      applyZoom();
    }
  } catch (err) {
    console.error("[Parser] Page render failed:", err);
    showToast("Render error: " + err.message, "error");
  } finally {
    state.isPageRendering = false;
    if (showModal) hideProgress();
  }
}

/**
 * Render any PDF background / sticker placeholders via PDF.js as 100% native vector SVG
 */
async function resolvePdfPlaceholders(containerElement) {
  if (!window.pdfjsLib) return;

  const placeholders = Array.from(containerElement.querySelectorAll(".gn-pdf-placeholder"));
  if (placeholders.length === 0) return;

  for (const node of placeholders) {
    try {
      const b64 = node.getAttribute("data-pdf-b64");
      const pageIdx = parseInt(node.getAttribute("data-pdf-page") || "0", 10);
      const width = parseFloat(node.getAttribute("data-width") || "100");
      const height = parseFloat(node.getAttribute("data-height") || "100");

      if (!b64) continue;

      let pdfDoc = pdfDocCache.get(b64);
      if (!pdfDoc) {
        const binaryString = atob(b64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        pdfDoc = await pdfjsLib.getDocument({ data: bytes }).promise;
        pdfDocCache.set(b64, pdfDoc);
      }

      const pdfPageNum = Math.min(Math.max(1, pageIdx + 1), pdfDoc.numPages);
      const pdfPage = await pdfDoc.getPage(pdfPageNum);
      const viewport = pdfPage.getViewport({ scale: 1.0 });

      // 1. Primary: Native Vector SVG rendering
      if (pdfjsLib.SVGGraphics) {
        try {
          const opList = await pdfPage.getOperatorList();
          const svgGfx = new pdfjsLib.SVGGraphics(pdfPage.commonObjs, pdfPage.objs);
          const svgElem = await svgGfx.getSVG(opList, viewport);

          svgElem.setAttribute("x", "0");
          svgElem.setAttribute("y", "0");
          svgElem.setAttribute("width", width.toFixed(2));
          svgElem.setAttribute("height", height.toFixed(2));
          svgElem.setAttribute("preserveAspectRatio", "none");

          node.parentNode.replaceChild(svgElem, node);
          continue;
        } catch (svgErr) {
          console.warn("[PDF.js] Vector SVGGraphics fallback to Canvas:", svgErr);
        }
      }

      // 2. Fallback: High-resolution raster render
      const scale = 2.0;
      const renderViewport = pdfPage.getViewport({ scale });
      const canvas = document.createElement("canvas");
      canvas.width = renderViewport.width;
      canvas.height = renderViewport.height;
      const ctx = canvas.getContext("2d");

      await pdfPage.render({
        canvasContext: ctx,
        viewport: renderViewport,
      }).promise;

      const pngDataUrl = canvas.toDataURL("image/png");
      const imgElem = document.createElementNS("http://www.w3.org/2000/svg", "image");
      imgElem.setAttribute("href", pngDataUrl);
      imgElem.setAttribute("x", "0");
      imgElem.setAttribute("y", "0");
      imgElem.setAttribute("width", width.toFixed(2));
      imgElem.setAttribute("height", height.toFixed(2));
      imgElem.setAttribute("preserveAspectRatio", "none");

      node.parentNode.replaceChild(imgElem, node);
    } catch (err) {
      console.warn("[PDF.js] Failed to render PDF placeholder:", err);
    }
  }
}

/**
 * Apply Zoom Scale to SVG stage
 */
function applyZoom() {
  el.svgStage.style.transform = `scale(${state.zoomLevel})`;
  el.zoomLevelText.textContent = `${Math.round(state.zoomLevel * 100)}%`;
}

/**
 * Calculate optimal zoom level to fit document in viewport with comfortable padding
 */
function fitToScreen() {
  if (!el.svgStage || !el.canvasContainer) return;
  const svg = el.svgStage.querySelector("svg");
  if (!svg) {
    state.zoomLevel = 1.0;
    applyZoom();
    return;
  }

  const containerW = el.canvasContainer.clientWidth;
  const containerH = el.canvasContainer.clientHeight;
  if (containerW <= 0 || containerH <= 0) return;

  // Available padding inside canvas container
  const paddingX = window.innerWidth <= 640 ? 16 : 40;
  const paddingY = window.innerWidth <= 640 ? 16 : 40;
  const availW = Math.max(80, containerW - paddingX);
  const availH = Math.max(80, containerH - paddingY);

  // Get SVG viewBox or native width/height
  let docW = parseFloat(svg.getAttribute("width")) || 612;
  let docH = parseFloat(svg.getAttribute("height")) || 792;
  const viewBox = svg.getAttribute("viewBox");
  if (viewBox) {
    const parts = viewBox.trim().split(/\s+/).map(Number);
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      docW = parts[2];
      docH = parts[3];
    }
  }

  const scaleW = availW / docW;
  const scaleH = availH / docH;
  let fitScale = Math.min(scaleW, scaleH);

  // Cap initial fit scale between 0.2 and 1.0 (don't upscale small vector pages, but scale down large docs)
  fitScale = Math.max(0.2, Math.min(fitScale, 1.0));

  state.zoomLevel = Math.round(fitScale * 100) / 100;
  applyZoom();
}

/**
 * Fetch and process sample archive with full progress feedback
 */
async function loadSample(samplePath, buttonElement) {
  el.sampleButtons.forEach(b => b.classList.remove("active", "is-loading"));
  if (buttonElement) {
    buttonElement.classList.add("active", "is-loading");
  }

  updateProgress({
    title: "Fetching Sample Archive",
    detail: `Downloading ${samplePath}...`,
    percent: 10,
    activeStep: 1,
    stepLabels: ["1. Download", "2. Decode Protobuf", "3. Render View"],
  });
  await yieldThread(30);

  try {
    const resp = await fetch(samplePath, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);
    const buffer = await resp.arrayBuffer();
    const filename = samplePath.split("/").pop();
    await processGoodNotesBuffer(buffer, filename);
  } catch (err) {
    console.error("[Parser] Failed to load sample:", err);
    showToast(`Could not load sample: ${err.message}`, "error");
    alert(`Could not load sample from ${samplePath}.\nPlease verify the file exists.`);
  } finally {
    if (buttonElement) buttonElement.classList.remove("is-loading");
    hideProgress();
  }
}

/**
 * Event Listeners Setup
 */
function setupEventListeners() {
  // Mobile Tab Switching
  if (el.tabBtnSidebar) {
    el.tabBtnSidebar.addEventListener("click", () => switchMobileTab("sidebar"));
  }
  if (el.tabBtnPreview) {
    el.tabBtnPreview.addEventListener("click", () => switchMobileTab("preview"));
  }

  // Language Switcher Buttons
  if (el.langBtnEn) {
    el.langBtnEn.addEventListener("click", () => setLanguage("en"));
  }
  if (el.langBtnZh) {
    el.langBtnZh.addEventListener("click", () => setLanguage("zh_TW"));
  }
  window.addEventListener("popstate", () => {
    setLanguage(detectLanguage(), false);
  });

  // Dropzone drag & drop
  el.dropzone.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!isGoodNotesFile(file.name)) {
        showToast(t("toastInvalidExt", file.name), "error", 5000);
        el.fileInput.value = "";
        return;
      }
      const reader = new FileReader();
      updateProgress({
        title: t("openingDoc"),
        detail: t("readingBytes", file.name, (file.size / 1024 / 1024).toFixed(2)),
        percent: 10,
        activeStep: 1,
      });
      reader.onload = () => processGoodNotesBuffer(reader.result, file.name);
      reader.readAsArrayBuffer(file);
    }
  });

  ["dragenter", "dragover"].forEach((evt) => {
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    el.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.dropzone.classList.remove("dragover");
    });
  });

  el.dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      if (!isGoodNotesFile(file.name)) {
        showToast(t("toastInvalidExt", file.name), "error", 5000);
        return;
      }
      const reader = new FileReader();
      updateProgress({
        title: t("openingDoc"),
        detail: t("readingBytes", file.name, (file.size / 1024 / 1024).toFixed(2)),
        percent: 10,
        activeStep: 1,
      });
      reader.onload = () => processGoodNotesBuffer(reader.result, file.name);
      reader.readAsArrayBuffer(file);
    }
  });

  // Sample Buttons
  el.sampleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const sample = btn.dataset.sample;
      if (sample) loadSample(sample, btn);
    });
  });

  // Pagination controls
  el.btnPrevPage.addEventListener("click", async () => {
    if (state.currentPageIndex > 0) {
      state.currentPageIndex--;
      await renderCurrentPage();
    }
  });

  el.btnNextPage.addEventListener("click", async () => {
    if (state.currentPageIndex < state.pageCount - 1) {
      state.currentPageIndex++;
      await renderCurrentPage();
    }
  });

  // Zoom controls
  el.btnZoomIn.addEventListener("click", () => {
    state.userHasZoomed = true;
    state.zoomLevel = Math.min(state.zoomLevel + 0.15, 3.0);
    applyZoom();
  });

  el.btnZoomOut.addEventListener("click", () => {
    state.userHasZoomed = true;
    state.zoomLevel = Math.max(state.zoomLevel - 0.15, 0.3);
    applyZoom();
  });

  el.btnZoomReset.addEventListener("click", () => {
    state.userHasZoomed = false;
    fitToScreen();
  });

  // Auto-fit on window resize
  window.addEventListener("resize", () => {
    if (!state.userHasZoomed && el.svgStage && !el.svgStage.classList.contains("hidden")) {
      fitToScreen();
    }
  });

  // Download Multi-page PDF
  if (el.btnDownloadPdf) {
    el.btnDownloadPdf.addEventListener("click", exportDocumentToPdf);
  }

  // Download SVG
  el.btnDownloadSvg.addEventListener("click", () => {
    if (!state.currentSvgString) return;
    const blob = new Blob([state.currentSvgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
    const filename = `${docBase}_page_${state.currentPageIndex + 1}.svg`;
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    showToast(t("toastSvgDownloaded", filename), "success");
  });

  // Download JSON
  el.btnDownloadJson.addEventListener("click", () => {
    if (!state.isReady) return;
    try {
      const exportJsonFn = state.pyodide.globals.get("export_json_ast");
      const jsonStr = exportJsonFn();
      const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
      const filename = `${docBase}_ast.json`;
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      showToast(t("toastJsonExported", filename), "success");
    } catch (err) {
      showToast("JSON export failed: " + err.message, "error");
    }
  });

  // Audio Player Event Listeners
  if (el.btnAudioPlay) el.btnAudioPlay.addEventListener("click", toggleAudioPlay);
  if (el.btnAudioRewind) el.btnAudioRewind.addEventListener("click", () => stepAudio(-5));
  if (el.btnAudioForward) el.btnAudioForward.addEventListener("click", () => stepAudio(5));
  if (el.btnAudioSpeed) el.btnAudioSpeed.addEventListener("click", cycleAudioSpeed);
  if (el.btnAudioAutoFlip) el.btnAudioAutoFlip.addEventListener("click", toggleAudioAutoFlip);
  if (el.audioSessionSelect) {
    el.audioSessionSelect.addEventListener("change", (e) => {
      selectAudioSession(parseInt(e.target.value, 10));
    });
  }
  if (el.audioModeSelect) {
    el.audioModeSelect.addEventListener("change", (e) => {
      setAudioMode(e.target.value);
    });
  }
  if (el.audioScrubber) {
    el.audioScrubber.addEventListener("input", (e) => {
      seekAudio(parseFloat(e.target.value) || 0);
    });
  }
  if (el.btnDownloadAudio) el.btnDownloadAudio.addEventListener("click", () => downloadAudioFile());
  if (el.btnDownloadHtml) el.btnDownloadHtml.addEventListener("click", downloadHtmlPlayer);
  if (el.btnDownloadAudioMain) el.btnDownloadAudioMain.addEventListener("click", () => downloadAudioFile());
  if (el.btnDownloadHtmlMain) el.btnDownloadHtmlMain.addEventListener("click", downloadHtmlPlayer);

  // Floating Canvas Audio Bar Listeners
  if (el.btnToolbarAudio) {
    el.btnToolbarAudio.addEventListener("click", () => {
      if (el.canvasAudioBar) {
        el.canvasAudioBar.classList.toggle("hidden");
      }
    });
  }
  if (el.cabBtnPlay) el.cabBtnPlay.addEventListener("click", toggleAudioPlay);
  if (el.cabBtnRewind) el.cabBtnRewind.addEventListener("click", () => stepAudio(-5));
  if (el.cabBtnForward) el.cabBtnForward.addEventListener("click", () => stepAudio(5));
  if (el.cabBtnSpeed) el.cabBtnSpeed.addEventListener("click", cycleAudioSpeed);
  if (el.cabBtnAutoFlip) el.cabBtnAutoFlip.addEventListener("click", toggleAudioAutoFlip);
  if (el.cabSessionSelect) {
    el.cabSessionSelect.addEventListener("change", (e) => {
      selectAudioSession(parseInt(e.target.value, 10));
    });
  }
  if (el.cabModeSelect) {
    el.cabModeSelect.addEventListener("change", (e) => {
      setAudioMode(e.target.value);
    });
  }
  if (el.cabScrubber) {
    el.cabScrubber.addEventListener("input", (e) => {
      seekAudio(parseFloat(e.target.value) || 0);
    });
  }
  if (el.cabBtnDownloadAudio) el.cabBtnDownloadAudio.addEventListener("click", () => downloadAudioFile());
  if (el.cabBtnDownloadHtml) el.cabBtnDownloadHtml.addEventListener("click", downloadHtmlPlayer);

  // CLI Options Event Listeners
  if (el.optParseAll) {
    el.optParseAll.addEventListener("change", async (e) => {
      state.cliOptions.parseAll = e.target.checked;
      if (state.currentDocBytes && state.pyodide) {
        try {
          const reloadFn = state.pyodide.globals.get("reload_pages");
          if (reloadFn) {
            const newCount = reloadFn(state.cliOptions.parseAll);
            state.pageCount = newCount || 1;
            state.pageSvgCache.clear();
            if (state.currentPageIndex >= state.pageCount) {
              state.currentPageIndex = Math.max(0, state.pageCount - 1);
            }

            // Refresh audio stroke page mappings with the new page collection
            const getRecsFn = state.pyodide.globals.get("get_document_recordings");
            if (getRecsFn) {
              const jsonStr = getRecsFn();
              const recordings = JSON.parse(jsonStr || "[]");
              if (recordings.length > 0) {
                initAudioPlayer(recordings);
              }
            }

            await renderCurrentPage(false);
            showToast(`${t("optParseAll")}: ${state.pageCount} ${state.pageCount > 1 ? "pages" : "page"}`, "info");
          }
        } catch (err) {
          console.error("[Parser] Reload pages error:", err);
        }
      }
    });
  }
  if (el.optStickyNotes) {
    el.optStickyNotes.addEventListener("change", (e) => {
      state.cliOptions.stickyNoteState = e.target.value;
      if (state.currentDocBytes) renderCurrentPage(false);
    });
  }
  if (el.optTextboxBorders) {
    el.optTextboxBorders.addEventListener("change", (e) => {
      state.cliOptions.textboxState = e.target.checked;
      if (state.currentDocBytes) renderCurrentPage(false);
    });
  }
  if (el.optFillShapes) {
    el.optFillShapes.addEventListener("change", (e) => {
      state.cliOptions.fillShapes = e.target.checked;
      if (state.currentDocBytes) renderCurrentPage(false);
    });
  }

  // Click-to-seek delegation on canvas
  if (el.svgStage) {
    el.svgStage.addEventListener("click", handleCanvasStrokeClick);
  }
}

/**
 * Format seconds to MM:SS string
 */
function formatTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

/**
 * Initialize Audio Player with parsed recording sessions
 */
function initAudioPlayer(recordings) {
  state.audio.recordings = recordings;
  state.audio.strokeMap.clear();

  // Calculate cumulative offsets and total duration
  let accum = 0;
  state.audio.recOffsets = [];
  recordings.forEach((rec, idx) => {
    state.audio.recOffsets.push(accum);
    accum += rec.duration || 0;

    // Index stroke timings
    if (Array.isArray(rec.stroke_timings)) {
      rec.stroke_timings.forEach((t) => {
        state.audio.strokeMap.set(t.stroke_uuid, {
          sessionIndex: idx,
          timestamp: t.timestamp,
          page_uuid: t.page_uuid,
        });
      });
    }
  });
  state.audio.totalDuration = accum;

  // Show audio containers and export buttons
  if (el.canvasAudioBar) el.canvasAudioBar.classList.remove("hidden");
  if (el.btnToolbarAudio) el.btnToolbarAudio.classList.remove("hidden");
  if (el.btnDownloadAudioMain) el.btnDownloadAudioMain.classList.remove("hidden");
  if (el.btnDownloadHtmlMain) el.btnDownloadHtmlMain.classList.remove("hidden");

  // Update session badge
  if (el.audioBadgeCount) {
    el.audioBadgeCount.textContent = `${recordings.length} ${recordings.length > 1 ? "Recordings" : "Recording"}`;
  }

  // Populate session dropdowns
  [el.audioSessionSelect, el.cabSessionSelect].forEach((sel) => {
    if (!sel) return;
    sel.innerHTML = "";
    if (recordings.length > 1) {
      const optAll = document.createElement("option");
      optAll.value = "-1";
      optAll.textContent = `${t("audioSessionAll")} (${formatTime(accum)})`;
      sel.appendChild(optAll);
    }
    recordings.forEach((rec, idx) => {
      const opt = document.createElement("option");
      opt.value = idx;
      opt.textContent = `Session ${idx + 1} (${formatTime(rec.duration)}, ${rec.stroke_timings ? rec.stroke_timings.length : 0} strokes)`;
      sel.appendChild(opt);
    });
  });

  // Default to Continuous All (-1) if multiple sessions, else 0
  const defaultIdx = recordings.length > 1 ? -1 : 0;
  selectAudioSession(defaultIdx, false);
}

/**
 * Reset / Hide Audio Player when non-audio document is loaded
 */
function resetAudioPlayer() {
  if (state.audio.audioEl) {
    state.audio.audioEl.pause();
    state.audio.audioEl.src = "";
  }
  state.audio.isPlaying = false;
  state.audio.recordings = [];
  state.audio.recOffsets = [];
  state.audio.strokeMap.clear();

  if (el.canvasAudioBar) el.canvasAudioBar.classList.add("hidden");
  if (el.btnToolbarAudio) el.btnToolbarAudio.classList.add("hidden");
  if (el.btnDownloadAudioMain) el.btnDownloadAudioMain.classList.add("hidden");
  if (el.btnDownloadHtmlMain) el.btnDownloadHtmlMain.classList.add("hidden");
  if (el.canvasContainer) el.canvasContainer.classList.remove("audio-sync-active", "mode-highlight", "mode-reveal", "mode-normal");
  if (el.cabIconPlay && el.cabIconPause) {
    el.cabIconPlay.classList.remove("hidden");
    el.cabIconPause.classList.add("hidden");
  }
}

/**
 * Switch Audio Mode (highlight / reveal / normal)
 */
function setAudioMode(mode) {
  state.audio.mode = mode || "highlight";
  if (el.audioModeSelect) el.audioModeSelect.value = state.audio.mode;
  if (el.cabModeSelect) el.cabModeSelect.value = state.audio.mode;
  if (el.canvasContainer) {
    el.canvasContainer.classList.remove("mode-highlight", "mode-reveal", "mode-normal");
    el.canvasContainer.classList.add(`mode-${state.audio.mode}`);
  }
  updateAudioSync();
}

/**
 * Select Audio Session (-1 for All Continuous, or specific session index)
 */
function selectAudioSession(sessionIdx, autoPlay = false) {
  if (!state.audio.recordings || state.audio.recordings.length === 0) return;
  state.audio.currentSessionIndex = sessionIdx;

  if (el.audioSessionSelect) el.audioSessionSelect.value = sessionIdx;
  if (el.cabSessionSelect) el.cabSessionSelect.value = sessionIdx;

  const targetDuration = sessionIdx === -1 ? state.audio.totalDuration : (state.audio.recordings[sessionIdx]?.duration || 0);

  // Set scrubber bounds
  if (el.audioScrubber) {
    el.audioScrubber.max = targetDuration || 100;
    el.audioScrubber.value = 0;
  }
  if (el.cabScrubber) {
    el.cabScrubber.max = targetDuration || 100;
    el.cabScrubber.value = 0;
  }
  if (el.audioDuration) el.audioDuration.textContent = formatTime(targetDuration);
  if (el.cabDuration) el.cabDuration.textContent = formatTime(targetDuration);
  if (el.toolbarAudioBadge) el.toolbarAudioBadge.textContent = formatTime(targetDuration);

  // Load first active audio segment
  const actualRecIdx = sessionIdx === -1 ? 0 : sessionIdx;
  loadAudioTrack(actualRecIdx, 0, autoPlay);

  setAudioMode(state.audio.mode);
}

/**
 * Load audio track for specific session
 */
function loadAudioTrack(recIdx, seekRelTime = 0, autoPlay = false) {
  if (!state.audio.recordings || recIdx < 0 || recIdx >= state.audio.recordings.length) return;
  const rec = state.audio.recordings[recIdx];

  if (rec.audio_base64) {
    state.audio.audioEl.src = `data:audio/mp4;base64,${rec.audio_base64}`;
  } else {
    state.audio.audioEl.src = "";
  }

  state.audio.activePlayingRecIdx = recIdx;
  state.audio.audioEl.playbackRate = state.audio.speedLevels[state.audio.speedIndex] || 1.0;

  state.audio.audioEl.onloadedmetadata = () => {
    if (seekRelTime > 0) {
      state.audio.audioEl.currentTime = seekRelTime;
    }
    if (autoPlay) {
      state.audio.audioEl.play().catch(() => {});
    }
    updateAudioSync();
  };

  // Hook playback events
  state.audio.audioEl.onplay = () => {
    state.audio.isPlaying = true;
    if (el.iconAudioPlay) el.iconAudioPlay.classList.add("hidden");
    if (el.iconAudioPause) el.iconAudioPause.classList.remove("hidden");
    if (el.cabIconPlay) el.cabIconPlay.classList.add("hidden");
    if (el.cabIconPause) el.cabIconPause.classList.remove("hidden");
    if (el.audioPlayerCard) el.audioPlayerCard.classList.add("playing");
    startAudioSyncLoop();
  };

  state.audio.audioEl.onpause = () => {
    state.audio.isPlaying = false;
    if (el.iconAudioPlay) el.iconAudioPlay.classList.remove("hidden");
    if (el.iconAudioPause) el.iconAudioPause.classList.add("hidden");
    if (el.cabIconPlay) el.cabIconPlay.classList.remove("hidden");
    if (el.cabIconPause) el.cabIconPause.classList.add("hidden");
    if (el.audioPlayerCard) el.audioPlayerCard.classList.remove("playing");
    updateAudioSync();
  };

  state.audio.audioEl.onended = () => {
    // In continuous mode (-1), automatically progress to next session
    if (state.audio.currentSessionIndex === -1 && state.audio.activePlayingRecIdx + 1 < state.audio.recordings.length) {
      loadAudioTrack(state.audio.activePlayingRecIdx + 1, 0, true);
      return;
    }
    state.audio.isPlaying = false;
    if (el.iconAudioPlay) el.iconAudioPlay.classList.remove("hidden");
    if (el.iconAudioPause) el.iconAudioPause.classList.add("hidden");
    if (el.cabIconPlay) el.cabIconPlay.classList.remove("hidden");
    if (el.cabIconPause) el.cabIconPause.classList.add("hidden");
    if (el.audioPlayerCard) el.audioPlayerCard.classList.remove("playing");
    updateAudioSync();
  };

  if (el.canvasContainer) {
    el.canvasContainer.classList.add("audio-sync-active");
  }
}

/**
 * Toggle Play / Pause
 */
function toggleAudioPlay() {
  if (!state.audio.audioEl.src && state.audio.recordings.length > 0) {
    selectAudioSession(state.audio.currentSessionIndex, true);
    return;
  }
  if (state.audio.audioEl.paused) {
    state.audio.audioEl.play().catch((e) => console.warn("[Audio] Play error:", e));
  } else {
    state.audio.audioEl.pause();
  }
}

/**
 * Step audio forward or backward by deltaSeconds (+5s / -5s)
 */
function stepAudio(deltaSeconds) {
  const curGlobalTime = getGlobalAudioTime();
  const maxDur = state.audio.currentSessionIndex === -1 ? state.audio.totalDuration : (state.audio.recordings[state.audio.currentSessionIndex]?.duration || 0);
  const targetTime = Math.max(0, Math.min(maxDur, curGlobalTime + deltaSeconds));
  seekAudio(targetTime, true);
}

/**
 * Cycle Playback Speed
 */
function cycleAudioSpeed() {
  state.audio.speedIndex = (state.audio.speedIndex + 1) % state.audio.speedLevels.length;
  const speed = state.audio.speedLevels[state.audio.speedIndex];
  state.audio.audioEl.playbackRate = speed;
  const speedText = `${speed.toFixed(speed % 1 === 0 ? 1 : 2)}x`;
  if (el.btnAudioSpeed) el.btnAudioSpeed.textContent = speedText;
  if (el.cabBtnSpeed) el.cabBtnSpeed.textContent = speedText;
}

/**
 * Toggle Auto Page Flip
 */
function toggleAudioAutoFlip() {
  state.audio.autoFlip = !state.audio.autoFlip;
  if (el.btnAudioAutoFlip) el.btnAudioAutoFlip.classList.toggle("active", state.audio.autoFlip);
  if (el.cabBtnAutoFlip) el.cabBtnAutoFlip.classList.toggle("active", state.audio.autoFlip);
}

/**
 * Get current global playback time across all sessions or single session
 */
function getGlobalAudioTime() {
  if (!state.audio.recordings || state.audio.recordings.length === 0) return 0;
  const trackTime = state.audio.audioEl ? state.audio.audioEl.currentTime : 0;
  if (state.audio.currentSessionIndex === -1) {
    const offset = state.audio.recOffsets[state.audio.activePlayingRecIdx || 0] || 0;
    return offset + trackTime;
  }
  return trackTime;
}

/**
 * Seek audio timeline (global time or session time)
 */
function seekAudio(targetTime, triggerAutoFlip = false) {
  if (!state.audio.recordings || state.audio.recordings.length === 0) return;

  if (state.audio.currentSessionIndex === -1) {
    // Determine which session targetTime falls into
    let targetRecIdx = 0;
    for (let i = 0; i < state.audio.recordings.length; i++) {
      const offset = state.audio.recOffsets[i];
      const dur = state.audio.recordings[i].duration;
      if (targetTime >= offset && (targetTime < offset + dur || i === state.audio.recordings.length - 1)) {
        targetRecIdx = i;
        break;
      }
    }
    const relTime = Math.max(0, targetTime - state.audio.recOffsets[targetRecIdx]);
    if (state.audio.activePlayingRecIdx !== targetRecIdx) {
      loadAudioTrack(targetRecIdx, relTime, state.audio.isPlaying);
    } else {
      state.audio.audioEl.currentTime = relTime;
    }
  } else {
    state.audio.audioEl.currentTime = targetTime;
  }
  updateAudioSync(triggerAutoFlip);
}

/**
 * Animation loop for continuous smooth sync
 */
function startAudioSyncLoop() {
  if (state.audio.animFrameId) cancelAnimationFrame(state.audio.animFrameId);
  const tick = () => {
    if (state.audio.isPlaying) {
      updateAudioSync(true);
      state.audio.animFrameId = requestAnimationFrame(tick);
    }
  };
  state.audio.animFrameId = requestAnimationFrame(tick);
}

/**
 * Match a target page UUID against document pages (supports exact & 28-char prefix match)
 */
function matchPageUuid(targetUuid) {
  if (!targetUuid || !state.pageUuids || state.pageUuids.length === 0) return null;
  const cleanTarget = String(targetUuid).replace(/[^a-zA-Z0-9]/g, "").toLowerCase();

  // 1. Exact match
  for (let idx = 0; idx < state.pageUuids.length; idx++) {
    const cleanPage = String(state.pageUuids[idx]).replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
    if (cleanPage === cleanTarget) return idx;
  }

  // 2. Prefix match (first 28 hex chars of 32-char UUID)
  for (let idx = 0; idx < state.pageUuids.length; idx++) {
    const cleanPage = String(state.pageUuids[idx]).replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
    if (cleanPage.length >= 28 && cleanTarget.length >= 28 && cleanPage.slice(0, 28) === cleanTarget.slice(0, 28)) {
      return idx;
    }
  }

  return null;
}

/**
 * Update dynamic stroke highlight, progress bars, clocks, and auto-flip
 */
function updateAudioSync(allowAutoFlip = false) {
  if (!state.audio.recordings || state.audio.recordings.length === 0) return;

  const curGlobalTime = getGlobalAudioTime();
  const curRecIdx = state.audio.activePlayingRecIdx || 0;
  const curRelTime = state.audio.audioEl ? state.audio.audioEl.currentTime : 0;
  const totalDur = state.audio.currentSessionIndex === -1 ? state.audio.totalDuration : (state.audio.recordings[state.audio.currentSessionIndex]?.duration || 0);

  // Update progress bars & clocks
  if (el.audioScrubber && !el.audioScrubber.matches(":active")) el.audioScrubber.value = curGlobalTime;
  if (el.cabScrubber && !el.cabScrubber.matches(":active")) el.cabScrubber.value = curGlobalTime;

  const pct = totalDur > 0 ? (curGlobalTime / totalDur) * 100 : 0;
  if (el.audioProgressBar) el.audioProgressBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  if (el.cabProgressBar) el.cabProgressBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;

  const timeStr = formatTime(curGlobalTime);
  if (el.audioCurrentTime) el.audioCurrentTime.textContent = timeStr;
  if (el.cabCurrentTime) el.cabCurrentTime.textContent = timeStr;

  // Auto page flip (only when actively playing or seeking, never when paused during manual pagination)
  const shouldAutoFlip = state.audio.autoFlip && (state.audio.isPlaying || allowAutoFlip) && !state.isPageRendering;
  if (shouldAutoFlip) {
    const curRec = state.audio.recordings[curRecIdx];
    if (curRec && Array.isArray(curRec.stroke_timings) && curRec.stroke_timings.length > 0) {
      let targetPage = null;
      for (let i = 0; i < curRec.stroke_timings.length; i++) {
        const st = curRec.stroke_timings[i];
        if (st.timestamp <= curRelTime + 0.05 && typeof st.page_index === "number" && st.page_index >= 0) {
          targetPage = st.page_index;
        }
      }

      if (targetPage !== null && targetPage !== state.currentPageIndex && targetPage < state.pageCount) {
        state.currentPageIndex = targetPage;
        renderCurrentPage(false);
        return;
      }
    }
  }

  // Update stroke CSS classes in current SVG
  if (!el.svgStage) return;
  const strokePaths = el.svgStage.querySelectorAll("path[data-stroke-id]");
  strokePaths.forEach((path) => {
    const strokeId = path.getAttribute("data-stroke-id");
    const timing = state.audio.strokeMap.get(strokeId);
    if (!timing) return;

    // Compare with current active session
    let isPlayed = false;
    let isActive = false;

    if (state.audio.currentSessionIndex === -1) {
      if (timing.sessionIndex < curRecIdx) {
        isPlayed = true;
      } else if (timing.sessionIndex === curRecIdx) {
        isPlayed = timing.timestamp <= curRelTime;
        isActive = isPlayed && (curRelTime - timing.timestamp < 0.8) && state.audio.isPlaying;
      } else {
        isPlayed = false;
      }
    } else {
      if (timing.sessionIndex === state.audio.currentSessionIndex) {
        isPlayed = timing.timestamp <= curRelTime;
        isActive = isPlayed && (curRelTime - timing.timestamp < 0.8) && state.audio.isPlaying;
      } else {
        isPlayed = false;
      }
    }

    if (isPlayed) {
      path.classList.add("stroke-played");
      path.classList.remove("stroke-future");
      if (isActive) {
        path.classList.add("stroke-active");
      } else {
        path.classList.remove("stroke-active");
      }
    } else {
      path.classList.remove("stroke-played", "stroke-active");
      path.classList.add("stroke-future");
    }
  });
}

/**
 * Handle user clicking any stroke on canvas to jump audio
 */
function handleCanvasStrokeClick(e) {
  const target = e.target.closest("path[data-stroke-id]");
  if (!target) return;
  const strokeId = target.getAttribute("data-stroke-id");
  const timing = state.audio.strokeMap.get(strokeId);
  if (!timing) return;

  if (state.audio.currentSessionIndex === -1) {
    const globalTime = (state.audio.recOffsets[timing.sessionIndex] || 0) + timing.timestamp;
    seekAudio(globalTime);
  } else {
    if (state.audio.currentSessionIndex !== timing.sessionIndex) {
      selectAudioSession(timing.sessionIndex, true);
    }
    seekAudio(timing.timestamp);
  }

  if (state.audio.audioEl.paused) {
    state.audio.audioEl.play().catch(() => {});
  }
  showToast(t("toastJumpedTime", timing.timestamp.toFixed(1)), "info", 1500);
}

/**
 * Helper to save base64 audio string as a downloadable file
 */
function saveBase64Audio(base64Str, filename) {
  const binaryStr = atob(base64Str);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "audio/mp4" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Download raw audio tracks (.m4a) - exports all sessions if multiple exist
 */
function downloadAudioFile(singleSessionIdx = null) {
  if (!state.isReady || !state.currentDocBytes) {
    showToast(t("noDocLoaded"), "info");
    return;
  }
  if (!state.audio.recordings || state.audio.recordings.length === 0) {
    showToast(state.lang === "zh_TW" ? "ℹ️ 此筆記未包含語音錄音。" : "ℹ️ No audio recordings found in this document.", "info", 3000);
    return;
  }
  try {
    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";

    // Single session explicitly requested or document has only 1 recording
    if (typeof singleSessionIdx === "number" || state.audio.recordings.length === 1) {
      const idx = typeof singleSessionIdx === "number" ? singleSessionIdx : state.audio.currentSessionIndex;
      const rec = state.audio.recordings[idx] || state.audio.recordings[0];
      if (rec && rec.audio_base64) {
        saveBase64Audio(rec.audio_base64, `${docBase}_session_${idx + 1}.m4a`);
        showToast(t("toastAudioExported", `${docBase}_session_${idx + 1}.m4a`), "success");
      }
      return;
    }

    // Multiple sessions: export all sessions with slight delay
    let downloadedCount = 0;
    state.audio.recordings.forEach((rec, idx) => {
      if (rec.audio_base64) {
        setTimeout(() => {
          saveBase64Audio(rec.audio_base64, `${docBase}_session_${idx + 1}.m4a`);
        }, idx * 250);
        downloadedCount++;
      }
    });
    showToast(
      state.lang === "zh_TW"
        ? `✓ 已下載共 ${downloadedCount} 個錄音音訊檔 (.m4a)`
        : `✓ Downloaded ${downloadedCount} audio recording files (.m4a)`,
      "success"
    );
  } catch (err) {
    showToast("Audio download failed: " + err.message, "error");
  }
}

/**
 * Download standalone interactive HTML player
 */
function downloadHtmlPlayer() {
  if (!state.isReady || !state.currentDocBytes) {
    showToast(t("noDocLoaded"), "info");
    return;
  }
  if (!state.audio.recordings || state.audio.recordings.length === 0) {
    showToast(state.lang === "zh_TW" ? "ℹ️ 此筆記未包含語音錄音。" : "ℹ️ No audio recordings found in this document.", "info", 3000);
    return;
  }
  try {
    const exportHtmlFn = state.pyodide.globals.get("export_recording_html");
    const htmlStr = exportHtmlFn(
      state.cliOptions.stickyNoteState,
      state.cliOptions.textboxState,
      state.cliOptions.fillShapes,
      state.cliOptions.parseAll
    );
    if (!htmlStr) {
      showToast("Failed to generate HTML player.", "error");
      return;
    }

    const blob = new Blob([htmlStr], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
    const filename = `${docBase}_player.html`;
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    showToast(t("toastHtmlExported", filename), "success");
  } catch (err) {
    showToast("HTML export failed: " + err.message, "error");
  }
}

/**
 * Convert SVG string into high-res Canvas element
 */
function svgToCanvas(svgString, width, height, scale = 2.0) {
  return new Promise((resolve, reject) => {
    // Guarantee proper XML / SVG namespaces
    let processedSvg = svgString;
    if (!processedSvg.includes('xmlns="http://www.w3.org/2000/svg"')) {
      processedSvg = processedSvg.replace(/<svg\b/, '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    if (!processedSvg.includes('xmlns:xlink=')) {
      processedSvg = processedSvg.replace(/<svg\b/, '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
    }

    const blob = new Blob([processedSvg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to rasterize SVG page to Canvas image."));
    };
    img.src = url;
  });
}

/**
 * Export full GoodNotes document as a single multi-page PDF in browser with non-blocking async rendering
 */
async function exportDocumentToPdf() {
  if (!state.isReady || !state.currentDocBytes || state.pageCount <= 0) {
    showToast(t("noDocLoaded"), "info");
    return;
  }

  if (!window.jspdf || !window.jspdf.jsPDF) {
    showToast("jsPDF library is not available.", "error");
    return;
  }

  if (el.btnDownloadPdf) el.btnDownloadPdf.classList.add("is-loading");

  const { jsPDF } = window.jspdf;
  let pdfDoc = null;

  try {
    const getBundleFn = state.pyodide.globals.get("get_page_bundle");

    updateProgress({
      title: t("exportingPdf"),
      detail: t("pdfInit", state.pageCount),
      percent: 5,
      activeStep: 1,
      stepLabels: [t("stepPrepare"), t("stepRenderPages"), t("stepSavePdf")],
    });
    await yieldThread(10);

    for (let i = 0; i < state.pageCount; i++) {
      const stepPct = Math.round(5 + ((i + 1) / state.pageCount) * 90);

      updateProgress({
        title: t("exportingPdf"),
        detail: t("pdfRenderingPage", i + 1, state.pageCount, stepPct),
        percent: stepPct,
        activeStep: 2,
      });

      // Non-blocking yield to keep browser UI 60fps responsive without locking
      await yieldThread(0);

      const bundleProxy = getBundleFn(
        i,
        state.cliOptions.stickyNoteState,
        state.cliOptions.textboxState,
        state.cliOptions.fillShapes
      );
      const bundle = bundleProxy.toJs();
      bundleProxy.destroy();

      const svgRaw = bundle.get("svg") || "";
      const pw = bundle.get("width") || 612;
      const ph = bundle.get("height") || 792;
      const orientation = pw > ph ? "landscape" : "portrait";

      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = svgRaw;

      // Resolve background & sticker PDF placeholders (cached)
      await resolvePdfPlaceholders(tempDiv);

      const svgElem = tempDiv.querySelector("svg");

      if (i === 0) {
        pdfDoc = new jsPDF({
          orientation: orientation,
          unit: "pt",
          format: [pw, ph],
          compress: true,
        });
      } else {
        pdfDoc.addPage([pw, ph], orientation);
      }

      // Attach tempDiv offscreen to DOM so svg2pdf can compute geometry and styles
      tempDiv.style.position = "absolute";
      tempDiv.style.left = "-99999px";
      tempDiv.style.top = "-99999px";
      tempDiv.style.visibility = "hidden";
      document.body.appendChild(tempDiv);

      // Convert SVG vector paths, shapes and text natively into PDF vector instructions
      let vectorRendered = false;
      if (svgElem) {
        try {
          if (typeof pdfDoc.svg === "function") {
            await pdfDoc.svg(svgElem, {
              x: 0,
              y: 0,
              width: pw,
              height: ph,
            });
            vectorRendered = true;
          } else if (window.svg2pdf && typeof window.svg2pdf.svg2pdf === "function") {
            await window.svg2pdf.svg2pdf(svgElem, pdfDoc, {
              x: 0,
              y: 0,
              width: pw,
              height: ph,
            });
            vectorRendered = true;
          } else if (typeof window.svg2pdf === "function") {
            await window.svg2pdf(svgElem, pdfDoc, {
              x: 0,
              y: 0,
              width: pw,
              height: ph,
            });
            vectorRendered = true;
          }
        } catch (vecErr) {
          console.warn("[PDF Export] Vector svg2pdf fallback to canvas:", vecErr);
        }
      }

      // High-resolution fallback if vector bridge unavailable
      if (!vectorRendered) {
        const canvas = await svgToCanvas(tempDiv.innerHTML, pw, ph, 2.0);
        const imgData = canvas.toDataURL("image/jpeg", 0.95);
        pdfDoc.addImage(imgData, "JPEG", 0, 0, pw, ph, undefined, "FAST");
      }

      // Clean up temp DOM container
      if (tempDiv.parentNode) {
        document.body.removeChild(tempDiv);
      }
    }

    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
    const filename = `${docBase}.pdf`;

    updateProgress({
      title: t("exportingPdf"),
      detail: t("pdfCompressing", filename),
      percent: 98,
      activeStep: 3,
    });
    await yieldThread(20);

    pdfDoc.save(filename);
    showToast(t("toastPdfSuccess", filename, state.pageCount), "success", 4500);
  } catch (err) {
    console.error("[PDF Export] Export failed:", err);
    showToast("Failed to export PDF: " + err.message, "error", 5000);
  } finally {
    if (el.btnDownloadPdf) el.btnDownloadPdf.classList.remove("is-loading");
    hideProgress();
  }
}

// Bootstrap Application
document.addEventListener("DOMContentLoaded", () => {
  switchMobileTab("sidebar");
  setLanguage(detectLanguage(), false);
  setupEventListeners();
  initPyodideRuntime();
});
