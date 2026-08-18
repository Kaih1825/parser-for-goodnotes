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
  svgStage: document.getElementById("svg-stage"),
  sampleButtons: document.querySelectorAll(".btn-sample"),
};

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

    // Try finding the wheel in root or dist directory
    const wheelCandidates = [
      "./goodnotes_document_parser-0.1.0-py3-none-any.whl",
      "../dist/goodnotes_document_parser-0.1.0-py3-none-any.whl",
      "./dist/goodnotes_document_parser-0.1.0-py3-none-any.whl",
    ];

    let loaded = false;
    for (const wheelUrl of wheelCandidates) {
      try {
        const resp = await fetch(wheelUrl, { method: "HEAD" });
        if (resp.ok) {
          await state.pyodide.loadPackage(wheelUrl);
          loaded = true;
          console.log(`[Parser] Loaded package wheel from ${wheelUrl}`);
          break;
        }
      } catch (e) {
        // continue
      }
    }

    if (!loaded) {
      // Fallback: try loading wheel directly from relative path
      try {
        await state.pyodide.loadPackage("./goodnotes_document_parser-0.1.0-py3-none-any.whl");
      } catch (err) {
        console.warn("[Parser] Wheel load fallback: trying standard import", err);
      }
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
    current_doc = GoodNotesDocument.from_bytes(bytes(data_bytes), filename=filename)
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
    alert("WebAssembly engine is still initializing. Please wait a moment.");
    return;
  }

  showLoading(`Parsing ${filename}...`);
  try {
    state.currentDocBytes = new Uint8Array(arrayBuffer);
    state.currentDocName = filename;

    // Send bytes to Python runtime
    const loadFn = state.pyodide.globals.get("load_document_bytes");
    const resultProxy = loadFn(state.currentDocBytes, filename);
    const docInfo = resultProxy.toJs();
    resultProxy.destroy();

    state.pageCount = docInfo.get("page_count") || 1;
    state.currentPageIndex = 0;

    // Render first page
    await renderCurrentPage();

    // Show stats card & hide empty state
    el.emptyState.classList.add("hidden");
    el.svgStage.classList.remove("hidden");
    el.docStatsCard.classList.remove("hidden");
  } catch (err) {
    console.error("[Parser] Document parsing failed:", err);
    alert("Error parsing .goodnotes document:\n" + err.message);
  } finally {
    hideLoading();
  }
}

/**
 * Render the current page SVG
 */
async function renderCurrentPage() {
  showLoading(`Rendering page ${state.currentPageIndex + 1}...`);
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
  } finally {
    hideLoading();
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
 * Fetch and process sample archive
 */
async function loadSample(samplePath, buttonElement) {
  el.sampleButtons.forEach(b => b.classList.remove("active"));
  if (buttonElement) buttonElement.classList.add("active");

  showLoading(`Fetching sample ${samplePath}...`);
  try {
    const resp = await fetch(samplePath);
    if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);
    const buffer = await resp.arrayBuffer();
    const filename = samplePath.split("/").pop();
    await processGoodNotesBuffer(buffer, filename);
  } catch (err) {
    console.error("[Parser] Failed to load sample:", err);
    alert(`Could not load sample from ${samplePath}.\nPlease verify the file exists.`);
  } finally {
    hideLoading();
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

  // Download SVG
  el.btnDownloadSvg.addEventListener("click", () => {
    if (!state.currentSvgString) return;
    const blob = new Blob([state.currentSvgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const docBase = state.currentDocName.replace(/\.goodnotes$/i, "") || "document";
    a.href = url;
    a.download = `${docBase}_page_${state.currentPageIndex + 1}.svg`;
    a.click();
    URL.revokeObjectURL(url);
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
      a.href = url;
      a.download = `${docBase}_ast.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("JSON export failed: " + err.message);
    }
  });
}

// Bootstrap Application
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  initPyodideRuntime();
});
