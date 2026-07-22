// YouDo Photo — Main Application
// ================================

(function () {
  'use strict';

  // === State ===
  const state = {
    rawFiles: [],
    refFiles: [],
    videoFile: null,
    currentStep: 1,
    gallery: [], // { file, thumbnail, score, status: 'pending'|'accepted'|'rejected' }
    params: {}
  };

  // === DOM refs ===
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // === Step navigation ===
  function goToStep(step) {
    state.currentStep = step;
    $$('.step-panel').forEach(p => p.classList.remove('active'));
    $(`#step${step}`).classList.add('active');

    $$('.step-btn').forEach((btn, i) => {
      btn.classList.remove('active');
      if (i + 1 === step) btn.classList.add('active');
      if (i + 1 < step) btn.classList.add('completed');
    });

    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (step === 3) buildGallery();
    if (step === 4) { buildExportPreview(); updateExportSummary(); }
  }

  // Step nav buttons
  $$('.step-btn').forEach(btn => {
    btn.addEventListener('click', () => goToStep(parseInt(btn.dataset.step)));
  });

  // Step action buttons
  $('#btnToStep2').addEventListener('click', () => goToStep(2));
  $('#btnToStep3').addEventListener('click', () => goToStep(3));
  $('#btnToStep4').addEventListener('click', () => goToStep(4));
  $('#btnBackTo1').addEventListener('click', () => goToStep(1));
  $('#btnBackTo2').addEventListener('click', () => goToStep(2));
  $('#btnBackTo3').addEventListener('click', () => goToStep(3));

  // === Dropzones ===
  function initDropzone(dropzoneEl, inputEl, onFiles) {
    dropzoneEl.addEventListener('click', () => inputEl.click());

    dropzoneEl.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzoneEl.classList.add('dragover');
    });

    dropzoneEl.addEventListener('dragleave', () => {
      dropzoneEl.classList.remove('dragover');
    });

    dropzoneEl.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzoneEl.classList.remove('dragover');
      onFiles(e.dataTransfer.files);
    });

    inputEl.addEventListener('change', () => {
      onFiles(inputEl.files);
      inputEl.value = '';
    });
  }

  // === RAW files ===
  initDropzone($('#dropzoneRaw'), $('#dropzoneRaw input[type="file"]'), (files) => {
    for (const f of files) {
      state.rawFiles.push(f);
    }
    updateRawInfo();
    updateNextButton();
  });

  function updateRawInfo() {
    const count = state.rawFiles.length;
    const size = state.rawFiles.reduce((s, f) => s + f.size, 0);
    $('#rawInfo .file-count').textContent = `${count} файлов`;
    $('#rawInfo .file-size').textContent = formatSize(size);

    const list = $('#rawList');
    list.innerHTML = '';
    state.rawFiles.forEach(f => {
      const item = document.createElement('div');
      item.className = 'file-list-item';
      item.innerHTML = `<span class="fname">${f.name}</span><span class="fsize">${formatSize(f.size)}</span>`;
      list.appendChild(item);
    });
  }

  // === Reference JPGs ===
  initDropzone($('#dropzoneRef'), $('#dropzoneRef input[type="file"]'), (files) => {
    for (const f of files) {
      state.refFiles.push(f);
    }
    updateRefPreview();
    updateNextButton();
  });

  function updateRefPreview() {
    const grid = $('#refPreview');
    grid.innerHTML = '';
    $('#refInfo .file-count').textContent = `${state.refFiles.length} файлов`;

    state.refFiles.forEach((f, i) => {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(f);
      img.title = f.name;
      if (i === 0) img.classList.add('starred');
      img.addEventListener('click', () => {
        grid.querySelectorAll('img').forEach(el => el.classList.remove('starred'));
        img.classList.add('starred');
      });
      grid.appendChild(img);
    });
  }

  // === Video ===
  initDropzone($('#dropzoneVideo'), $('#dropzoneVideo input[type="file"]'), (files) => {
    if (files.length > 0) {
      state.videoFile = files[0];
      updateVideoPreview();
      updateNextButton();
    }
  });

  function updateVideoPreview() {
    const container = $('#videoPreview');
    container.innerHTML = '';
    if (!state.videoFile) return;

    const video = document.createElement('video');
    video.src = URL.createObjectURL(state.videoFile);
    video.controls = true;
    video.muted = true;
    container.appendChild(video);

    $('#videoInfo .file-count').textContent = state.videoFile.name;
  }

  // === Next button state ===
  function updateNextButton() {
    $('#btnToStep2').disabled = state.rawFiles.length === 0;
  }

  // === Range sliders ===
  $$('input[type="range"]').forEach(range => {
    const display = $(`.range-val[data-for="${range.id}"]`);
    if (display) {
      const suffix = display.textContent.includes('%') ? '%' : '';
      range.addEventListener('input', () => {
        display.textContent = range.value + suffix;
      });
    }
  });

  // === Temperature toggle ===
  const paramTemp = $('#paramTemp');
  const paramTempK = $('#paramTempK');
  paramTemp.addEventListener('change', () => {
    const isManual = paramTemp.value === 'manual';
    paramTempK.disabled = !isManual;
    paramTempK.style.display = isManual ? '' : 'none';
  });
  // Init: hide if auto
  if (paramTemp.value !== 'manual') {
    paramTempK.style.display = 'none';
  }

  // === Export resolution toggle ===
  $('#exportResolution').addEventListener('change', (e) => {
    $('#customResRow').hidden = e.target.value !== 'custom';
  });

  // === Export naming toggle ===
  $('#exportNaming').addEventListener('change', (e) => {
    $('#customNameRow').hidden = e.target.value !== 'custom';
  });

  // === File type helpers ===
  const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif'];
  const RAW_EXTS = ['.cr3', '.cr2', '.nef', '.arw', '.raf', '.rw2', '.dng', '.raw', '.orf', '.srw', '.pef'];

  function getExt(name) {
    return ('.' + name.split('.').pop()).toLowerCase();
  }

  function isDisplayable(name) {
    return IMAGE_EXTS.includes(getExt(name));
  }

  function isRaw(name) {
    return RAW_EXTS.includes(getExt(name));
  }

  // === Gallery ===
  function buildGallery() {
    const gallery = $('#gallery');
    gallery.innerHTML = '';

    if (state.rawFiles.length === 0) {
      gallery.innerHTML = '<div class="gallery-empty"><p>Нет файлов для модерации</p></div>';
      return;
    }

    // Build thumbnails: use JPG refs if available, else try objectURL, else placeholder
    const refThumbs = state.refFiles.map(f => URL.createObjectURL(f));

    state.gallery = state.rawFiles.map((file, i) => {
      let thumbnail;
      if (isDisplayable(file.name)) {
        thumbnail = URL.createObjectURL(file);
      } else if (refThumbs.length > 0) {
        // Cycle through reference JPGs as preview
        thumbnail = refThumbs[i % refThumbs.length];
      } else {
        thumbnail = null; // will render placeholder
      }

      return {
        file,
        index: i,
        thumbnail,
        score: Math.floor(Math.random() * 40) + 60, // TODO: real AI scoring
        status: 'pending'
      };
    });

    renderGallery();
  }

  function renderGallery(filter = 'all') {
    const gallery = $('#gallery');
    gallery.innerHTML = '';

    const filtered = filter === 'all'
      ? state.gallery
      : state.gallery.filter(g => g.status === filter);

    if (filtered.length === 0) {
      gallery.innerHTML = '<div class="gallery-empty"><p>Нет файлов по этому фильтру</p></div>';
      return;
    }

    filtered.forEach((item) => {
      const card = document.createElement('div');
      card.className = `gallery-card ${item.status}`;
      card.dataset.index = item.index;

      const scoreClass = item.score >= 80 ? 'high' : item.score >= 60 ? 'mid' : 'low';
      const statusIcon = item.status === 'accepted' ? '✅' : item.status === 'rejected' ? '❌' : '🔍';

      const deleteBtn = item.status === 'accepted'
        ? `<button class="card-delete-btn" data-idx="${item.index}" title="Удалить">🗑️</button>`
        : '';

      const ext = getExt(item.file.name).toUpperCase().replace('.', '');
      const imgHtml = item.thumbnail
        ? `<img src="${item.thumbnail}" alt="${item.file.name}" loading="lazy">`
        : `<div class="card-placeholder"><span class="card-placeholder-ext">${ext}</span><span class="card-placeholder-name">${item.file.name}</span></div>`;

      card.innerHTML = `
        ${imgHtml}
        ${deleteBtn}
        <div class="gallery-card-footer">
          <span class="gallery-card-score ${scoreClass}">${item.score}%</span>
          <span class="gallery-card-status">${statusIcon}</span>
        </div>
      `;

      card.addEventListener('click', (e) => {
        if (e.target.closest('.card-delete-btn')) return;
        openViewer(item.index);
      });

      const delBtn = card.querySelector('.card-delete-btn');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const idx = parseInt(delBtn.dataset.idx);
          state.gallery[idx].status = 'rejected';
          renderGallery(getCurrentFilter());
        });
      }

      gallery.appendChild(card);
    });

    updateStats();
  }

  function updateStats() {
    const total = state.gallery.length;
    const accepted = state.gallery.filter(g => g.status === 'accepted').length;
    const rejected = state.gallery.filter(g => g.status === 'rejected').length;
    const pending = state.gallery.filter(g => g.status === 'pending').length;

    $('#statTotal').textContent = total;
    $('#statAccepted').textContent = accepted;
    $('#statRejected').textContent = rejected;
    $('#statPending').textContent = pending;
  }

  // === Filters ===
  $$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderGallery(btn.dataset.filter);
    });
  });

  // === Bulk actions ===
  $('#btnAcceptAll').addEventListener('click', () => {
    const threshold = parseInt($('#paramThreshold').value);
    state.gallery.forEach(item => {
      if (item.score >= threshold) item.status = 'accepted';
    });
    renderGallery(getCurrentFilter());
  });

  $('#btnResetAll').addEventListener('click', () => {
    state.gallery.forEach(item => item.status = 'pending');
    renderGallery(getCurrentFilter());
  });

  function getCurrentFilter() {
    const active = $('.filter-btn.active');
    return active ? active.dataset.filter : 'all';
  }

  // === Fullscreen Viewer ===
  let viewerIndex = 0;

  function openViewer(index) {
    viewerIndex = index;
    const item = state.gallery[index];

    const ext = getExt(item.file.name).toUpperCase().replace('.', '');
    if (item.thumbnail) {
      $('#viewerImage').innerHTML = `<img src="${item.thumbnail}" alt="${item.file.name}">`;
    } else {
      $('#viewerImage').innerHTML = `<div class="card-placeholder" style="width:100%;height:60vh;border-radius:8px"><span class="card-placeholder-ext" style="font-size:64px">${ext}</span><span class="card-placeholder-name" style="font-size:16px">${item.file.name}</span></div>`;
    }

    const scoreColor = item.score >= 80 ? 'var(--success)' : item.score >= 60 ? 'var(--warning)' : 'var(--danger)';
    $('#viewerScore').innerHTML = `
      <div style="font-size:32px;font-weight:700;color:${scoreColor}">${item.score}%</div>
      <div style="font-size:13px;color:var(--text-muted);margin-top:4px">${item.file.name}</div>
    `;

    if (item.thumbnail) {
      drawHistogram(item.thumbnail);
    } else {
      clearHistogram();
    }

    $('#fullscreenViewer').hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeViewer() {
    $('#fullscreenViewer').hidden = true;
    document.body.style.overflow = '';
    renderGallery(getCurrentFilter());
  }

  $('#viewerClose').addEventListener('click', closeViewer);
  $('#viewerPrev').addEventListener('click', () => {
    viewerIndex = Math.max(0, viewerIndex - 1);
    openViewer(viewerIndex);
  });
  $('#viewerNext').addEventListener('click', () => {
    viewerIndex = Math.min(state.gallery.length - 1, viewerIndex + 1);
    openViewer(viewerIndex);
  });

  $('#viewerAccept').addEventListener('click', () => {
    state.gallery[viewerIndex].status = 'accepted';
    viewerIndex < state.gallery.length - 1 ? openViewer(++viewerIndex) : closeViewer();
  });

  $('#viewerReject').addEventListener('click', () => {
    state.gallery[viewerIndex].status = 'rejected';
    viewerIndex < state.gallery.length - 1 ? openViewer(++viewerIndex) : closeViewer();
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    if ($('#fullscreenViewer').hidden) return;
    if (e.key === 'Escape') closeViewer();
    if (e.key === 'ArrowLeft') { viewerIndex = Math.max(0, viewerIndex - 1); openViewer(viewerIndex); }
    if (e.key === 'ArrowRight') { viewerIndex = Math.min(state.gallery.length - 1, viewerIndex + 1); openViewer(viewerIndex); }
    if (e.key === 'a' || e.key === 'ф') { state.gallery[viewerIndex].status = 'accepted'; viewerIndex < state.gallery.length - 1 ? openViewer(++viewerIndex) : closeViewer(); }
    if (e.key === 'r' || e.key === 'к') { state.gallery[viewerIndex].status = 'rejected'; viewerIndex < state.gallery.length - 1 ? openViewer(++viewerIndex) : closeViewer(); }
  });

  // === Histogram ===
  function clearHistogram() {
    const canvas = $('#histogramCanvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 256;
    canvas.height = 100;
    ctx.clearRect(0, 0, 256, 100);
    ctx.fillStyle = 'rgba(91, 127, 255, 0.1)';
    ctx.fillRect(0, 0, 256, 100);
    ctx.fillStyle = 'rgba(91, 127, 255, 0.4)';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Нет превью', 128, 55);
  }

  function drawHistogram(src) {
    const canvas = $('#histogramCanvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const w = 256, h = 100;
      canvas.width = w;
      canvas.height = h;

      const tempCanvas = document.createElement('canvas');
      const tCtx = tempCanvas.getContext('2d');
      tempCanvas.width = img.width;
      tempCanvas.height = img.height;
      tCtx.drawImage(img, 0, 0);
      const data = tCtx.getImageData(0, 0, img.width, img.height).data;

      const bins = new Uint32Array(256);
      for (let i = 0; i < data.length; i += 4) {
        const gray = Math.round(data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114);
        bins[gray]++;
      }

      const max = Math.max(...bins);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = 'rgba(91, 127, 255, 0.5)';
      for (let i = 0; i < 256; i++) {
        const barH = (bins[i] / max) * h;
        ctx.fillRect(i, h - barH, 1, barH);
      }
    };
    img.src = src;
  }

  // === Export Preview ===
  function buildExportPreview() {
    const grid = $('#exportPreviewGrid');
    grid.innerHTML = '';
    const accepted = state.gallery.filter(g => g.status === 'accepted');
    $('#exportPreviewCount').textContent = accepted.length;

    if (accepted.length === 0) {
      grid.innerHTML = '<div class="export-preview-empty"><p>Нет принятых фото. Вернитесь на шаг 3 и примите кадры.</p></div>';
      return;
    }

    accepted.forEach((item) => {
      const el = document.createElement('div');
      el.className = 'export-preview-item';
      el.innerHTML = `
        <img src="${item.thumbnail}" alt="${item.file.name}">
        <button class="remove-btn" data-idx="${item.index}" title="Удалить из экспорта">✕</button>
      `;
      el.querySelector('.remove-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        state.gallery[item.index].status = 'rejected';
        buildExportPreview();
        updateExportSummary();
      });
      grid.appendChild(el);
    });
  }

  // === Export ===
  function updateExportSummary() {
    const accepted = state.gallery.filter(g => g.status === 'accepted').length;
    $('#summaryAccepted').textContent = accepted;
    $('#summaryFormat').textContent = $('#exportFormat').value.toUpperCase();
    $('#summaryQuality').textContent = $('#exportQuality').value;
    const avgSizeMB = 15; // rough estimate per processed JPG
    $('#summarySize').textContent = `~${(accepted * avgSizeMB).toLocaleString()} МБ`;
  }

  $('#exportFormat').addEventListener('change', updateExportSummary);
  $('#exportQuality').addEventListener('input', updateExportSummary);

  $('#btnExport').addEventListener('click', async () => {
    const accepted = state.gallery.filter(g => g.status === 'accepted');
    if (accepted.length === 0) {
      alert('Нет принятых кадров для экспорта');
      return;
    }

    const progressEl = $('#exportProgress');
    const fillEl = $('#progressFill');
    const textEl = $('#progressText');
    progressEl.hidden = false;

    // TODO: real processing pipeline
    for (let i = 0; i < accepted.length; i++) {
      const pct = Math.round(((i + 1) / accepted.length) * 100);
      fillEl.style.width = pct + '%';
      textEl.textContent = `${pct}% — обработка ${i + 1}/${accepted.length}`;
      await sleep(80); // simulate processing
    }

    textEl.textContent = 'Готово! Скачивание...';
    await sleep(500);

    // Simulate ZIP download
    alert(`Экспорт завершён: ${accepted.length} файлов\n(Реальная конвертация RAW → JPG будет подключена позже)`);
    progressEl.hidden = true;
    fillEl.style.width = '0%';
  });

  // === Utils ===
  function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' Б';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' МБ';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' ГБ';
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // === Init ===
  goToStep(1);

})();
