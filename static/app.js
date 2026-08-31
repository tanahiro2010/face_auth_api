const API_BASE = "";

// ---------- タブ切り替え ----------
const tabButtons = document.querySelectorAll(".tab-btn");
tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    stopAllCameras();
    if (btn.dataset.tab === "list") loadPeople();
  });
});

// ---------- カメラ／画像取得ウィジェット ----------
const captures = {}; // target名 -> { getBlob }
const activeStreams = [];

function stopAllCameras() {
  activeStreams.forEach((stream) => stream.getTracks().forEach((t) => t.stop()));
  activeStreams.length = 0;
}

function setupCaptureWidgets() {
  document.querySelectorAll(".capture").forEach((container) => {
    const template = document.getElementById("capture-template");
    const node = template.content.cloneNode(true);
    container.appendChild(node);

    const target = container.dataset.target;
    const video = container.querySelector("video");
    const canvas = container.querySelector("canvas");
    const snapshot = container.querySelector(".snapshot");
    const startBtn = container.querySelector(".cam-start");
    const shotBtn = container.querySelector(".cam-shot");
    const retakeBtn = container.querySelector(".cam-retake");
    const fileInput = container.querySelector(".file-input");

    let currentBlob = null;

    function showSnapshot(blob, url) {
      currentBlob = blob;
      snapshot.src = url;
      snapshot.hidden = false;
      video.hidden = true;
      shotBtn.hidden = true;
      retakeBtn.hidden = false;
      startBtn.hidden = true;
    }

    function resetToStart() {
      snapshot.hidden = true;
      video.hidden = false;
      shotBtn.hidden = true;
      retakeBtn.hidden = true;
      startBtn.hidden = false;
      currentBlob = null;
      fileInput.value = "";
    }

    startBtn.addEventListener("click", async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        activeStreams.push(stream);
        video.srcObject = stream;
        video.hidden = false;
        snapshot.hidden = true;
        startBtn.hidden = true;
        shotBtn.hidden = false;
        retakeBtn.hidden = true;
      } catch (err) {
        alert("カメラを起動できませんでした: " + err.message);
      }
    });

    shotBtn.addEventListener("click", () => {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d").drawImage(video, 0, 0);
      const stream = video.srcObject;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      canvas.toBlob(
        (blob) => showSnapshot(blob, URL.createObjectURL(blob)),
        "image/jpeg",
        0.92
      );
    });

    retakeBtn.addEventListener("click", () => {
      resetToStart();
    });

    fileInput.addEventListener("change", () => {
      const file = fileInput.files[0];
      if (!file) return;
      const stream = video.srcObject;
      if (stream) stream.getTracks().forEach((t) => t.stop());
      showSnapshot(file, URL.createObjectURL(file));
    });

    captures[target] = { getBlob: () => currentBlob };
  });
}

// ---------- 追加情報の行編集 ----------
function setupInfoRows() {
  const rowsContainer = document.getElementById("info-rows");
  const rowTemplate = document.getElementById("info-row-template");
  const addBtn = document.getElementById("add-info-row");

  function addRow() {
    const node = rowTemplate.content.cloneNode(true);
    node.querySelector(".remove-row").addEventListener("click", (e) => {
      e.target.closest(".info-row").remove();
    });
    rowsContainer.appendChild(node);
  }

  addBtn.addEventListener("click", addRow);
  addRow();
}

function collectInfo() {
  const info = {};
  document.querySelectorAll("#info-rows .info-row").forEach((row) => {
    const key = row.querySelector(".info-key").value.trim();
    const value = row.querySelector(".info-value").value.trim();
    if (key) info[key] = value;
  });
  return info;
}

// ---------- 結果表示 ----------
function showResult(el, message, isError) {
  el.textContent = message;
  el.classList.remove("ok", "error");
  el.classList.add(isError ? "error" : "ok");
}

// ---------- 登録フォーム ----------
document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultEl = document.getElementById("register-result");
  const blob = captures.register.getBlob();
  if (!blob) {
    showResult(resultEl, "顔写真を撮影するか、ファイルを選択してください。", true);
    return;
  }

  const formData = new FormData();
  formData.append("name", document.getElementById("register-name").value);
  formData.append("info", JSON.stringify(collectInfo()));
  formData.append("image", blob, "face.jpg");

  try {
    const res = await fetch(`${API_BASE}/faces/register`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "登録に失敗しました");
    showResult(resultEl, `登録しました: ${data.name} (id: ${data.id})`, false);
    e.target.reset();
    document.querySelectorAll("#info-rows .info-row").forEach((r, i) => i > 0 && r.remove());
    document.querySelectorAll("#info-rows .info-row input").forEach((i) => (i.value = ""));
  } catch (err) {
    showResult(resultEl, err.message, true);
  }
});

// ---------- 識別フォーム ----------
document.getElementById("identify-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultEl = document.getElementById("identify-result");
  const blob = captures.identify.getBlob();
  if (!blob) {
    showResult(resultEl, "顔写真を撮影するか、ファイルを選択してください。", true);
    return;
  }

  const formData = new FormData();
  formData.append("image", blob, "face.jpg");

  try {
    const res = await fetch(`${API_BASE}/faces/identify`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "識別に失敗しました");
    const infoText = Object.entries(data.person.info || {})
      .map(([k, v]) => `${k}: ${v}`)
      .join("\n");
    showResult(
      resultEl,
      `名前: ${data.person.name}\n類似度: ${data.similarity.toFixed(3)}` +
        (infoText ? `\n${infoText}` : ""),
      false
    );
  } catch (err) {
    showResult(resultEl, err.message, true);
  }
});

// ---------- 一覧タブ ----------
async function loadPeople() {
  const tbody = document.querySelector("#people-table tbody");
  tbody.innerHTML = `<tr><td colspan="4">読み込み中...</td></tr>`;
  try {
    const res = await fetch(`${API_BASE}/faces`);
    const people = await res.json();
    if (!people.length) {
      tbody.innerHTML = `<tr><td colspan="4">登録者がいません</td></tr>`;
      return;
    }
    tbody.innerHTML = "";
    people.forEach((p) => {
      const tr = document.createElement("tr");
      const infoText = Object.entries(p.info || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      tr.innerHTML = `
        <td>${escapeHtml(p.name)}</td>
        <td>${escapeHtml(infoText)}</td>
        <td>${new Date(p.created_at).toLocaleString("ja-JP")}</td>
        <td><button class="delete-btn" data-id="${p.id}">削除</button></td>
      `;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("削除しますか？")) return;
        await fetch(`${API_BASE}/faces/${btn.dataset.id}`, { method: "DELETE" });
        loadPeople();
      });
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4">読み込みに失敗しました: ${escapeHtml(err.message)}</td></tr>`;
  }
}

document.getElementById("refresh-list").addEventListener("click", loadPeople);

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- 初期化 ----------
setupCaptureWidgets();
setupInfoRows();
