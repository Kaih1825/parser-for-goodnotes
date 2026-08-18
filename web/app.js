/**
 * GoodNotes WebAssembly Document Parser & Vector SVG Viewer
 * Powered by Pyodide (WASM Python)
 */

// Application State
const state = {
  pyodide: null,
  isReady: false,
  currentDocBytes: null,
  currentDocName: "",
  pageCount: 0,
  currentPageIndex: 0,
  currentDocMeta: null,
  currentSvgString: "",
  zoomLevel: 1.0,
};

// DOM Elements
const el = {
  runtimeStatus: document.getElementById("runtime-status"),
  statusText: document.querySelector("#runtime-status .status-text"),
  dropzone: document.getElementById("dropzone"),
  fileInput: document.getElementById("file-input"),
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
  svgStage: document.getElementById("svg-stage"),
  sampleButtons: document.querySelectorAll(".btn-sample"),
};

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
 * Initialize Pyodide Runtime & Python Parser Package
 */
async function initPyodideRuntime() {
  try {
    updateStatus("loading", "Initializing WebAssembly Python...");
    
    state.pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.2/full/",
    });

    updateStatus("loading", "Loading GoodNotes Parser Package...");

    // Try finding and unpacking the wheel from candidates
    const ts = Date.now();
    const wheelCandidates = [
      `./goodnotes_document_parser-0.1.0-py3-none-any.whl?v=${ts}`,
      `../dist/goodnotes_document_parser-0.1.0-py3-none-any.whl?v=${ts}`,
      `./dist/goodnotes_document_parser-0.1.0-py3-none-any.whl?v=${ts}`,
    ];

    let loaded = false;
    for (const wheelUrl of wheelCandidates) {
      try {
        const resp = await fetch(wheelUrl, { cache: "no-store" });
        if (resp.ok) {
          const wheelBuffer = await resp.arrayBuffer();
          await state.pyodide.unpackArchive(wheelBuffer, "whl");
          loaded = true;
          console.log(`[Parser] Successfully unpacked package wheel from ${wheelUrl}`);
          break;
        }
      } catch (e) {
        console.warn(`[Parser] Attempt to fetch ${wheelUrl} failed:`, e);
      }
    }

    if (!loaded) {
      throw new Error("Could not find or load goodnotes_document_parser wheel package.");
    }

    // Define Python bridge helpers
    await state.pyodide.runPythonAsync(`
import io
import json
import tempfile
from pathlib import Path
from goodnotes_re.archive import GoodNotesDocument
from goodnotes_re.export import write_svg

current_doc = None
current_pages = []

def load_document_bytes(data_bytes, filename="doc.goodnotes"):
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
        current_pages = current_doc.pages(parse_all=True)
    except Exception:
        current_pages = current_doc.pages()
    
    return {
        "page_count": len(current_pages),
        "filename": filename,
    }

def get_page_svg(page_idx):
    global current_doc, current_pages
    if not current_doc or not current_pages or page_idx < 0 or page_idx >= len(current_pages):
        return ""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        written = write_svg(current_doc, tmpdir, fill_shapes=True, parse_all=True)
        if 0 <= page_idx < len(written):
            return Path(written[page_idx]).read_text(encoding="utf-8")
        elif written:
            return Path(written[0]).read_text(encoding="utf-8")
    return ""

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

def export_json_ast():
    global current_doc
    if not current_doc:
        return "{}"
    return json.dumps(current_doc.as_json(), ensure_ascii=False, indent=2)
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

/**
 * Parse and load GoodNotes binary ArrayBuffer into Pyodide
 */
async function processGoodNotesBuffer(arrayBuffer, filename) {
  if (!state.isReady) {
    showToast("WebAssembly engine is still initializing. Please wait...", "info");
    return;
  }

  const mbSize = (arrayBuffer.byteLength / 1024 / 1024).toFixed(2);
  updateProgress({
    title: "Opening GoodNotes Document",
    detail: `Reading "${filename}" (${mbSize} MB)...`,
    percent: 15,
    activeStep: 1,
    stepLabels: ["1. Read Archive", "2. Decode Protobuf", "3. Render View"],
  });
  await yieldThread(40);

  try {
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
    const resultProxy = loadFn(state.currentDocBytes, filename);
    const docInfo = resultProxy.toJs();
    resultProxy.destroy();

    state.pageCount = docInfo.get("page_count") || 1;
    state.currentPageIndex = 0;

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

/**
 * Render the current page SVG
 */
async function renderCurrentPage(showModal = true) {
  if (showModal) {
    updateProgress({
      title: `Rendering Page ${state.currentPageIndex + 1}`,
      detail: "Building vector strokes and PDF template background...",
      percent: 50,
      activeStep: 3,
      stepLabels: ["1. Read Archive", "2. Decode Protobuf", "3. Render View"],
    });
    await yieldThread(20);
  }

  try {
    const getSvgFn = state.pyodide.globals.get("get_page_svg");
    const getStatsFn = state.pyodide.globals.get("get_page_stats");

    // Fetch SVG text
    state.currentSvgString = getSvgFn(state.currentPageIndex);

    // Fetch Page Stats
    const statsProxy = getStatsFn(state.currentPageIndex);
    const stats = statsProxy.toJs();
    statsProxy.destroy();

    // Inject SVG into DOM
    el.svgStage.innerHTML = state.currentSvgString;

    // Resolve any PDF background / sticker placeholders using PDF.js
    await resolvePdfPlaceholders(el.svgStage);
    state.currentSvgString = el.svgStage.innerHTML;

    // Update stats UI
    el.statPages.textContent = `${state.pageCount}`;
    el.statCurPage.textContent = `${state.currentPageIndex + 1} / ${state.pageCount}`;
    el.statStrokes.textContent = `${stats.get("strokes_count") || 0}`;
    const w = Math.round(stats.get("width") || 0);
    const h = Math.round(stats.get("height") || 0);
    el.statDimensions.textContent = `${w} × ${h}`;

    // Update Pagination Toolbar
    el.pageIndicator.textContent = `Page ${state.currentPageIndex + 1} / ${state.pageCount}`;
    el.btnPrevPage.disabled = state.currentPageIndex <= 0;
    el.btnNextPage.disabled = state.currentPageIndex >= state.pageCount - 1;

    // Reset zoom transformation
    applyZoom();
  } catch (err) {
    console.error("[Parser] Page render failed:", err);
    showToast("Render error: " + err.message, "error");
  } finally {
    if (showModal) hideProgress();
  }
}

/**
 * Render any PDF background / sticker placeholders via PDF.js into sharp SVG <image> elements
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

      // Decode base64 to binary Uint8Array
      const binaryString = atob(b64);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Load PDF document using PDF.js
      const pdfDoc = await pdfjsLib.getDocument({ data: bytes }).promise;
      const pdfPageNum = Math.min(Math.max(1, pageIdx + 1), pdfDoc.numPages);
      const pdfPage = await pdfDoc.getPage(pdfPageNum);

      // Render at 2x scale for sharp high-DPI display
      const scale = 2.0;
      const viewport = pdfPage.getViewport({ scale });

      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");

      await pdfPage.render({
        canvasContext: ctx,
        viewport: viewport,
      }).promise;

      const pngDataUrl = canvas.toDataURL("image/png");

      // Replace placeholder with standard SVG <image>
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
  // Dropzone drag & drop
  el.dropzone.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      updateProgress({
        title: "Reading File",
        detail: `Loading ${file.name}...`,
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
      const reader = new FileReader();
      updateProgress({
        title: "Reading Dropped File",
        detail: `Reading ${file.name}...`,
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
    state.zoomLevel = Math.min(state.zoomLevel + 0.15, 3.0);
    applyZoom();
  });

  el.btnZoomOut.addEventListener("click", () => {
    state.zoomLevel = Math.max(state.zoomLevel - 0.15, 0.3);
    applyZoom();
  });

  el.btnZoomReset.addEventListener("click", () => {
    state.zoomLevel = 1.0;
    applyZoom();
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
    showToast(`✓ Downloaded ${filename}`, "success");
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
      showToast(`✓ Exported ${filename}`, "success");
    } catch (err) {
      showToast("JSON export failed: " + err.message, "error");
    }
  });
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
    showToast("No document is currently loaded.", "info");
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
    const getSvgFn = state.pyodide.globals.get("get_page_svg");
    const getStatsFn = state.pyodide.globals.get("get_page_stats");

    updateProgress({
      title: "Exporting Multi-Page PDF",
      detail: `Initializing PDF builder for ${state.pageCount} page(s)...`,
      percent: 5,
      activeStep: 1,
      stepLabels: ["1. Prepare", "2. Render Pages", "3. Save PDF"],
    });
    await yieldThread(40);

    for (let i = 0; i < state.pageCount; i++) {
      const stepPct = Math.round(10 + ((i + 1) / state.pageCount) * 80);

      updateProgress({
        title: "Exporting Multi-Page PDF",
        detail: `Rendering page ${i + 1} of ${state.pageCount} (${stepPct}%)...`,
        percent: stepPct,
        activeStep: 2,
      });
      // Yield main thread to allow browser UI paint & 60fps animation
      await yieldThread(30);

      const svgRaw = getSvgFn(i);
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = svgRaw;

      // Resolve background & sticker PDF placeholders
      await resolvePdfPlaceholders(tempDiv);

      const statsProxy = getStatsFn(i);
      const stats = statsProxy.toJs();
      statsProxy.destroy();

      const pw = stats.get("width") || 612;
      const ph = stats.get("height") || 792;
      const orientation = pw > ph ? "landscape" : "portrait";

      const canvas = await svgToCanvas(tempDiv.innerHTML, pw, ph, 2.0);
      const imgData = canvas.toDataURL("image/jpeg", 0.95);

      if (i === 0) {
        pdfDoc = new jsPDF({
          orientation: orientation,
          unit: "pt",
          format: [pw, ph],
          compress: true,
        });
        pdfDoc.addImage(imgData, "JPEG", 0, 0, pw, ph, undefined, "FAST");
      } else {
        pdfDoc.addPage([pw, ph], orientation);
        pdfDoc.addImage(imgData, "JPEG", 0, 0, pw, ph, undefined, "FAST");
      }

      await yieldThread(20);
    }

    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
    const filename = `${docBase}.pdf`;

    updateProgress({
      title: "Exporting Multi-Page PDF",
      detail: `Compressing and saving "${filename}"...`,
      percent: 98,
      activeStep: 3,
    });
    await yieldThread(50);

    pdfDoc.save(filename);
    showToast(`✓ Successfully exported "${filename}" (${state.pageCount} pages)`, "success", 4500);
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
  setupEventListeners();
  initPyodideRuntime();
});
