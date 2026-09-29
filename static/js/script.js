document.addEventListener('DOMContentLoaded', function () {
  initAlerts();
  initToTop();
  initWordmark();
  initFlaps();
  initGallery();
  initTargetCursor();
  initUploadForm();
});

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// Сообщения закрываются крестиком и сами исчезают через 6 секунд
function initAlerts() {
  document.querySelectorAll('.alert').forEach(alert => {
    if (alert.id === 'upload-status') return; // управляется формой загрузки

    const dismiss = () => {
      alert.classList.add('alert-hidden');
      setTimeout(() => alert.remove(), 450);
    };

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'alert-close';
    close.setAttribute('aria-label', 'Закрыть уведомление');
    close.textContent = '×';
    close.addEventListener('click', dismiss);
    alert.appendChild(close);

    setTimeout(dismiss, 6000);
  });
}

function initToTop() {
  const button = document.querySelector('.to-top');
  if (!button) return;

  const sync = () => button.classList.toggle('visible', window.scrollY > 1200);
  window.addEventListener('scroll', sync, { passive: true });
  sync();

  button.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: reduceMotion.matches ? 'auto' : 'smooth' });
  });
}

function initGallery() {
  const gallery = document.getElementById('gallery');
  if (!gallery) return;

  gallery.querySelectorAll('.card').forEach(revealCard);
  const feed = setupInfiniteScroll(gallery);
  initLightbox(gallery, feed);
}

// Карточка проявляется, когда её превью загрузилось и она доехала до экрана
function revealCard(card) {
  if (inViewObserver) inViewObserver.observe(card);
  else card.classList.add('inview');
  const img = card.querySelector('img');
  const show = () => card.classList.add('loaded');
  if (!img || (img.complete && img.naturalWidth)) {
    show();
    return;
  }
  img.addEventListener('load', show, { once: true });
  img.addEventListener('error', show, { once: true });
}

function initLightbox(gallery, feed) {
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = lightbox ? lightbox.querySelector('img') : null;
  if (!lightbox || !lightboxImg) return;

  // Лайтбокс работает по уже загруженным карточкам и догружает
  // следующую страницу ленты, когда листание доходит до конца.
  let allPhotos = [];
  let currentIndex = -1;
  let lastFocused = null;
  let closing = false;
  const ENLARGE_MS = 300;

  const closeBtn = lightbox.querySelector('.lightbox-close');
  const prevBtn = lightbox.querySelector('.lightbox-prev');
  const nextBtn = lightbox.querySelector('.lightbox-next');
  const counterEl = lightbox.querySelector('.lightbox-counter');
  const counter = counterEl ? createSplitFlap(counterEl) : null;
  const zoom = setupGestures(lightbox, lightboxImg, {
    prev: prevPhoto,
    next: nextPhoto,
    close: closeLightbox,
  });

  function getVisiblePhotos() {
    return Array.from(gallery.querySelectorAll('.card img'))
      .map(img => ({
        url: img.src,
        full_url: img.dataset.full,
        medium_url: img.dataset.medium || '',
        alt: img.alt || '',
        el: img, // источник и цель перехода открытия/закрытия
      }))
      .filter(photo => photo.url && photo.full_url);
  }

  // Телефону хватает версии 1600px, 2560px нужны только большим экранам
  function pickFullUrl(photo) {
    const needed = Math.max(window.innerWidth, window.innerHeight) * (window.devicePixelRatio || 1);
    return photo.medium_url && needed <= 1700 ? photo.medium_url : photo.full_url;
  }

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function updateCounter() {
    if (!counter) return;
    if (currentIndex < 0 || !allPhotos.length) return;
    counter.set(`${pad(currentIndex + 1)} / ${pad(allPhotos.length)}`);
  }

  function preloadNeighbors(index) {
    [index - 1, index + 1].forEach(i => {
      if (i >= 0 && i < allPhotos.length) {
        new Image().src = pickFullUrl(allPhotos[i]);
      }
    });
  }

  function showPhoto(index, direction) {
    if (index < 0 || index >= allPhotos.length) return;
    currentIndex = index;
    const photo = allPhotos[index];
    zoom.reset();

    // Направленный вход нового кадра: класс перевешивается с reflow,
    // чтобы анимация проигрывалась на каждом перелистывании.
    lightboxImg.classList.remove('slide-from-left', 'slide-from-right');
    if (direction) {
      void lightboxImg.offsetWidth;
      lightboxImg.classList.add(direction === 'next' ? 'slide-from-right' : 'slide-from-left');
    }

    // Blur-up: сразу показываем миниатюру из кэша, полную версию подменяем по загрузке
    const fullUrl = pickFullUrl(photo);
    lightboxImg.classList.add('is-loading');
    lightboxImg.src = photo.url;
    lightboxImg.alt = photo.alt;

    const full = new Image();
    full.onload = () => {
      if (currentIndex !== index) return;
      lightboxImg.src = fullUrl;
      lightboxImg.classList.remove('is-loading');
    };
    full.onerror = () => {
      if (currentIndex === index) lightboxImg.classList.remove('is-loading');
    };
    full.src = fullUrl;

    updateCounter();
    preloadNeighbors(index);
  }

  // Переходы в духе DomeGallery (React Bits): фото вырастает из карточки,
  // одновременно проявляясь, а при закрытии сжимается в неё, растворяясь;
  // затем сама карточка мягко проявляется на месте. FLIP через WAAPI.
  const canAnimate = () => typeof lightboxImg.animate === 'function' && !reduceMotion.matches;

  // Трансформация, которая кладёт кадр лайтбокса ровно на прямоугольник карточки
  function frameToCard(frame, cardEl) {
    const rect = cardEl.getBoundingClientRect();
    const sx = rect.width / frame.width;
    const sy = rect.height / frame.height;
    return `translate(${rect.left - frame.left}px, ${rect.top - frame.top}px) scale(${sx}, ${sy})`;
  }

  function finishClose() {
    if (!closing) return;
    closing = false;
    lightbox.setAttribute('aria-hidden', 'true');
    lightboxImg.removeAttribute('src');
    lightboxImg.style.opacity = '';
    lightboxImg.style.transformOrigin = '';
    lightboxImg.getAnimations().forEach(animation => animation.cancel());
    currentIndex = -1;
    updateCounter();
  }

  function zoomFromCard(sourceEl) {
    if (!canAnimate() || !sourceEl) return;

    const fly = () => {
      const to = lightboxImg.getBoundingClientRect();
      if (!to.width || !sourceEl.getBoundingClientRect().width) return;
      sourceEl.style.visibility = 'hidden';
      lightboxImg.style.transformOrigin = 'top left';
      const animation = lightboxImg.animate(
        [
          { transform: frameToCard(to, sourceEl), opacity: 0 },
          { transform: 'none', opacity: 1 },
        ],
        { duration: ENLARGE_MS, easing: 'ease' }
      );
      settleAnimation(animation, ENLARGE_MS + 200, () => {
        lightboxImg.style.transformOrigin = '';
        sourceEl.style.visibility = '';
      });
    };

    // Миниатюра почти всегда уже в кэше - размер известен синхронно;
    // иначе прячем кадр до load, чтобы он не мигнул в полный размер.
    if (lightboxImg.complete && lightboxImg.naturalWidth) {
      fly();
    } else {
      lightboxImg.style.opacity = '0';
      lightboxImg.addEventListener('load', () => {
        lightboxImg.style.opacity = '';
        fly();
      }, { once: true });
    }
  }

  function openLightbox(index) {
    if (closing) finishClose();
    lastFocused = document.activeElement;
    lightbox.classList.add('active');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    showPhoto(index);
    zoomFromCard(allPhotos[index] ? allPhotos[index].el : null);
    if (closeBtn) closeBtn.focus({ preventScroll: true });
  }

  function closeLightbox() {
    if (closing || !lightbox.classList.contains('active')) return;
    closing = true;
    zoom.reset();

    const sourceEl = currentIndex >= 0 && allPhotos[currentIndex] ? allPhotos[currentIndex].el : null;

    lightbox.classList.remove('active');
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus({ preventScroll: true });
    }
    lastFocused = null;

    const hasImage = Boolean(lightboxImg.getAttribute('src'));
    if (canAnimate() && hasImage && sourceEl && sourceEl.isConnected) {
      const to = sourceEl.getBoundingClientRect();
      const from = lightboxImg.getBoundingClientRect();
      if (to.width > 0 && to.bottom > 0 && to.top < window.innerHeight && from.width > 0) {
        sourceEl.style.visibility = 'hidden';
        lightboxImg.style.transformOrigin = 'top left';
        const animation = lightboxImg.animate(
          [
            { transform: 'none', opacity: 1 },
            { transform: frameToCard(from, sourceEl), opacity: 0 },
          ],
          { duration: ENLARGE_MS, easing: 'ease-out', fill: 'forwards' }
        );
        settleAnimation(animation, ENLARGE_MS + 200, () => {
          finishClose();
          sourceEl.style.visibility = '';
          sourceEl.animate([{ opacity: 0 }, { opacity: 1 }], { duration: ENLARGE_MS, easing: 'ease-out' });
        });
        return;
      }
    }

    if (canAnimate() && hasImage) {
      // Карточка вне экрана - мягкое сжатие с растворением
      const animation = lightboxImg.animate(
        [
          { transform: 'none', opacity: 1 },
          { transform: 'scale(0.94)', opacity: 0 },
        ],
        { duration: ENLARGE_MS, easing: 'ease-out', fill: 'forwards' }
      );
      settleAnimation(animation, ENLARGE_MS + 200, finishClose);
      return;
    }

    finishClose();
  }

  function prevPhoto() {
    if (currentIndex > 0) showPhoto(currentIndex - 1, 'prev');
  }

  async function nextPhoto() {
    if (currentIndex < allPhotos.length - 1) {
      showPhoto(currentIndex + 1, 'next');
      return;
    }
    if (!feed.hasMore()) return;
    const appended = await feed.loadMore();
    if (!appended || !lightbox.classList.contains('active')) return;
    allPhotos = getVisiblePhotos();
    if (currentIndex < allPhotos.length - 1) {
      showPhoto(currentIndex + 1, 'next');
    } else {
      updateCounter();
    }
  }

  gallery.addEventListener('click', e => {
    const card = e.target.closest('.card');
    const img = card && card.querySelector('img');
    if (!img) return;
    allPhotos = getVisiblePhotos();
    const index = allPhotos.findIndex(photo => photo.el === img);
    if (index !== -1) openLightbox(index);
  });

  closeBtn.addEventListener('click', e => { e.stopPropagation(); closeLightbox(); });
  prevBtn.addEventListener('click', e => { e.stopPropagation(); prevPhoto(); });
  nextBtn.addEventListener('click', e => { e.stopPropagation(); nextPhoto(); });

  // Клик по фону закрывает, если это не конец жеста
  lightbox.addEventListener('click', e => {
    if (e.target === lightbox && !zoom.justGestured()) closeLightbox();
  });

  document.addEventListener('keydown', e => {
    if (!lightbox.classList.contains('active')) return;
    if (e.key === 'ArrowLeft') prevPhoto();
    if (e.key === 'ArrowRight') nextPhoto();
    if (e.key === 'Escape') closeLightbox();
  });

  // Focus trap: Tab не покидает модальный диалог
  lightbox.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const focusable = Array.from(lightbox.querySelectorAll('button')).filter(el => el.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
}

// Жесты лайтбокса на Pointer Events: щипок и двойной тап увеличивают фото,
// увеличенное фото двигается пальцем или мышью; без увеличения горизонтальный
// свайп листает, свайп вниз закрывает.
function setupGestures(lightbox, img, actions) {
  const MAX_SCALE = 4;
  const DOUBLE_TAP_SCALE = 2.5;
  const pointers = new Map();
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let mode = null; // 'pinch' | 'pan' | 'swipe'
  let start = null;
  let axis = null;
  let lastTap = null;
  let gesturedAt = 0;

  const center = () => ({
    x: img.offsetLeft + img.offsetWidth / 2,
    y: img.offsetTop + img.offsetHeight / 2,
  });

  function clampPan() {
    const maxX = (img.offsetWidth * (scale - 1)) / 2;
    const maxY = (img.offsetHeight * (scale - 1)) / 2;
    tx = Math.max(-maxX, Math.min(maxX, tx));
    ty = Math.max(-maxY, Math.min(maxY, ty));
  }

  function apply() {
    const zoomed = scale > 1.001;
    img.classList.toggle('is-zoomed', zoomed);
    img.style.transform = zoomed ? `translate(${tx}px, ${ty}px) scale(${scale})` : '';
  }

  // Масштаб вокруг точки экрана: точка под пальцем остаётся на месте
  function zoomAt(point, nextScale, fromScale = scale, from = { x: tx, y: ty }) {
    const c = center();
    const qx = (point.x - c.x - from.x) / fromScale;
    const qy = (point.y - c.y - from.y) / fromScale;
    scale = Math.max(1, Math.min(MAX_SCALE, nextScale));
    tx = point.x - c.x - scale * qx;
    ty = point.y - c.y - scale * qy;
    clampPan();
    apply();
  }

  function reset() {
    scale = 1;
    tx = 0;
    ty = 0;
    pointers.clear();
    mode = null;
    img.classList.remove('is-dragging');
    img.style.opacity = '';
    apply();
  }

  const points = () => Array.from(pointers.values());
  const distance = ([a, b]) => Math.hypot(a.x - b.x, a.y - b.y);
  const midpoint = ([a, b]) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });

  function beginSinglePointer(p, pointerType) {
    start = { x: p.x, y: p.y, tx, ty, moved: false };
    axis = null;
    if (scale > 1.001) mode = 'pan';
    else mode = pointerType === 'mouse' ? null : 'swipe';
  }

  lightbox.addEventListener('pointerdown', e => {
    if (e.target.closest('button') || !lightbox.classList.contains('active')) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try {
      lightbox.setPointerCapture(e.pointerId);
    } catch (err) {
      // указатель уже отпущен - жест продолжится без захвата
    }

    if (pointers.size === 2) {
      const pts = points();
      start = { d: distance(pts), m: midpoint(pts), scale, tx, ty, moved: true };
      mode = 'pinch';
      img.classList.remove('is-dragging');
      img.style.opacity = '';
    } else if (pointers.size === 1) {
      beginSinglePointer({ x: e.clientX, y: e.clientY }, e.pointerType);
    }
  });

  lightbox.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (mode === 'pinch' && pointers.size >= 2) {
      const pts = points();
      zoomAt(midpoint(pts), start.scale * (distance(pts) / start.d), start.scale, {
        x: start.tx + (midpoint(pts).x - start.m.x),
        y: start.ty + (midpoint(pts).y - start.m.y),
      });
      return;
    }

    const dx = e.clientX - start.x;
    const dy = e.clientY - start.y;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) start.moved = true;

    if (mode === 'pan') {
      tx = start.tx + dx;
      ty = start.ty + dy;
      clampPan();
      apply();
    } else if (mode === 'swipe') {
      // Ось жеста фиксируется один раз - диагональ не листает и не закрывает одновременно
      if (!axis) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      }
      if (axis !== 'x') return;
      img.classList.remove('slide-from-left', 'slide-from-right');
      img.classList.add('is-dragging');
      img.style.transform = `translateX(${dx}px)`;
      img.style.opacity = String(Math.max(0.35, 1 - Math.abs(dx) / window.innerWidth));
    }
  });

  function endPointer(e, cancelled) {
    if (!pointers.has(e.pointerId)) return;
    pointers.delete(e.pointerId);
    const moved = start && start.moved;
    if (moved) gesturedAt = performance.now();

    if (mode === 'pinch') {
      if (scale < 1.05) reset();
      if (pointers.size === 1) beginSinglePointer(points()[0], e.pointerType);
      else mode = null;
      return;
    }

    if (mode === 'swipe' && !cancelled) {
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      img.classList.remove('is-dragging');
      img.style.transform = '';
      img.style.opacity = '';
      if (axis === 'x' && Math.abs(dx) > 60) {
        if (dx > 0) actions.prev();
        else actions.next();
      } else if (axis === 'y' && dy > 70) {
        actions.close();
      }
    }
    mode = null;

    // Двойной тап по фото: увеличить в точке касания или вернуть исходный размер
    if (!moved && !cancelled && e.target === img) {
      const now = performance.now();
      const tap = { x: e.clientX, y: e.clientY, t: now };
      if (lastTap && now - lastTap.t < 300 && Math.hypot(tap.x - lastTap.x, tap.y - lastTap.y) < 30) {
        if (scale > 1.001) reset();
        else zoomAt(tap, DOUBLE_TAP_SCALE);
        lastTap = null;
        gesturedAt = now;
      } else {
        lastTap = tap;
      }
    }
  }

  lightbox.addEventListener('pointerup', e => endPointer(e, false));
  lightbox.addEventListener('pointercancel', e => {
    endPointer(e, true);
    img.classList.remove('is-dragging');
    if (scale <= 1.001) {
      img.style.transform = '';
      img.style.opacity = '';
    }
  });

  return {
    reset,
    justGestured: () => performance.now() - gesturedAt < 350,
  };
}

function setupInfiniteScroll(gallery) {
  const sentinel = document.getElementById('gallery-sentinel');
  const status = document.getElementById('gallery-feed-status');
  if (!sentinel) {
    return { loadMore: () => Promise.resolve(false), hasMore: () => false };
  }

  let inflight = null;
  let nextPage = parsePositiveInt(sentinel.dataset.currentPage, 1) + 1;
  let hasMore = sentinel.dataset.hasNext === 'true';
  let retryBlockedUntil = 0;

  const setFeedStatus = (state, message = '') => {
    if (!status) return;
    status.textContent = message;
    // Ошибка даёт явную кнопку повтора вместо "прокрутите ещё раз"
    if (state === 'error') {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'feed-retry';
      retry.textContent = 'Повторить';
      retry.addEventListener('click', () => {
        retryBlockedUntil = 0;
        loadMore();
      });
      status.appendChild(retry);
    }
    status.hidden = !message;
  };

  // Возвращает промис с true, если новые карточки добавлены -
  // этим же методом пользуется лайтбокс при достижении конца списка.
  function loadMore() {
    if (inflight) return inflight;
    if (!hasMore || Date.now() < retryBlockedUntil) return Promise.resolve(false);
    inflight = fetchNextPage().finally(() => {
      inflight = null;
    });
    return inflight;
  }

  async function fetchNextPage() {
    setFeedStatus('loading', 'Загрузка...');

    // Keyset-курсор от последней карточки; data-ts передаётся вместе с id,
    // чтобы курсор пережил удаление этого фото. page - фолбэк без карточек.
    const cards = gallery.querySelectorAll('.card[data-id]');
    const lastCard = cards.length ? cards[cards.length - 1] : null;
    const params = lastCard
      ? { after: lastCard.dataset.id, after_ts: lastCard.dataset.ts || '' }
      : { page: nextPage };

    try {
      const response = await fetch(buildUrlWithQuery(window.location.pathname, params), {
        headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      const newCards = (Array.isArray(data.photos) ? data.photos : [])
        .map(createGalleryCard)
        .filter(Boolean);
      newCards.forEach(card => {
        gallery.appendChild(card);
        revealCard(card);
      });

      hasMore = Boolean(data.has_next);
      if (data.page !== undefined) nextPage = parsePositiveInt(data.page, nextPage) + 1;
      setFeedStatus('idle');
      if (!hasMore && observer) observer.disconnect();
      return newCards.length > 0;
    } catch (err) {
      retryBlockedUntil = Date.now() + 2000;
      setFeedStatus('error', 'Не удалось загрузить фото.');
      console.error('Ошибка загрузки ленты:', err);
      return false;
    }
  }

  const observer = 'IntersectionObserver' in window && hasMore
    ? new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) loadMore();
      }, { rootMargin: '0px 0px 800px 0px' })
    : null;
  if (observer) observer.observe(sentinel);

  return { loadMore, hasMore: () => hasMore };
}

function createGalleryCard(photo) {
  if (!photo || !photo.url || !photo.full_url) return null;
  const label = photo.alt_text || 'Фотография';

  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'card';
  card.dataset.id = String(photo.id);
  if (photo.uploaded_at) card.dataset.ts = String(photo.uploaded_at);
  card.setAttribute('aria-label', `Открыть фото: ${label}`);

  const img = document.createElement('img');
  img.loading = 'lazy';
  img.decoding = 'async';
  img.src = photo.url;
  img.alt = label;
  img.dataset.full = photo.full_url;
  img.dataset.medium = photo.medium_url || '';

  const width = parsePositiveInt(photo.width, 0);
  const height = parsePositiveInt(photo.height, 0);
  if (width && height) {
    img.width = width;
    img.height = height;
    card.style.setProperty('--r', (width / height).toFixed(4));
  }

  card.appendChild(img);
  return card;
}

function initUploadForm() {
  const form = document.getElementById('upload-form');
  const fileInput = document.getElementById('id_files');
  const preview = document.getElementById('preview-container');
  const submitBtn = document.getElementById('submit-btn');
  const statusBox = document.getElementById('upload-status');

  if (!form || !fileInput || !preview || !submitBtn) return;

  let selectedFiles = [];
  let uploading = false;
  const previewCache = new Map(); // file -> Promise<dataURL> (не перекодируем повторно)
  const previewNodes = new Map(); // file -> wrapper element
  const fileLabelText = form.querySelector('.dropzone-text');
  const defaultLabelText = fileLabelText ? fileLabelText.textContent : '';
  submitBtn.disabled = true;

  // Файл, уроненный мимо зоны, не должен открываться браузером
  ['dragover', 'drop'].forEach(ev =>
      window.addEventListener(ev, e => e.preventDefault())
  );

  fileInput.addEventListener('change', handleFileSelect);
  form.addEventListener('submit', handleFormSubmit);

  // Drag and drop
  const dropZone = fileInput.closest('.dropzone');
  if (dropZone) {
      ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => {
          dropZone.addEventListener(ev, preventDefaults);
      });

      ['dragenter', 'dragover'].forEach(ev => {
          dropZone.addEventListener(ev, () => dropZone.classList.add('dragover'));
      });

      ['dragleave', 'drop'].forEach(ev => {
          dropZone.addEventListener(ev, () => dropZone.classList.remove('dragover'));
      });

      dropZone.addEventListener('drop', handleDrop);
  }

  function handleFileSelect(e) {
      const files = Array.from(e.target.files);
      processFiles(files);
  }

  function handleDrop(e) {
      const files = Array.from(e.dataTransfer.files);
      processFiles(files);
  }

  function processFiles(files) {
      // Лимит приходит с сервера через data-атрибут, не хардкодится
      const maxUploadMb = parseInt(form.dataset.maxUploadMb, 10) || 100;
      const maxBytes = maxUploadMb * 1024 * 1024;
      const validFiles = files.filter(f => f.size <= maxBytes);
      const oversized = files.filter(f => f.size > maxBytes);

      if (oversized.length) {
          const names = oversized
              .map(f => `${f.name} (${Math.round(f.size / 1024 / 1024)}МБ)`)
              .join(', ');
          setUploadStatus(
              `Файлы больше ${maxUploadMb}МБ не добавлены: ${names}`,
              'danger'
          );
      } else {
          setUploadStatus('', '');
      }

      // Повторный выбор того же файла не создаёт дубликат в пакете
      const known = new Set(
          selectedFiles.map(f => `${f.name}|${f.size}|${f.lastModified}`)
      );
      const freshFiles = validFiles.filter(f => {
          const key = `${f.name}|${f.size}|${f.lastModified}`;
          if (known.has(key)) return false;
          known.add(key);
          return true;
      });

      selectedFiles = selectedFiles.concat(freshFiles);
      updateFileInput();
      renderPreviews();
  }

  function updateFileInput() {
      const dt = new DataTransfer();
      selectedFiles.forEach(f => dt.items.add(f));
      fileInput.files = dt.files;
  }

  async function renderPreviews() {
      preview.innerHTML = '';
      previewNodes.clear();

      for (let i = 0; i < selectedFiles.length; i++) {
          const file = selectedFiles[i];
          const wrapper = document.createElement('div');
          wrapper.className = 'preview-wrapper';

          const img = document.createElement('img');
          img.className = 'preview-image';
          img.alt = file.name;

          const removeBtn = document.createElement('button');
          removeBtn.type = 'button';
          removeBtn.className = 'remove-preview';
          removeBtn.setAttribute('aria-label', `Удалить ${file.name}`);
          removeBtn.textContent = '×';
          removeBtn.addEventListener('click', () => {
              if (uploading || wrapper.classList.contains('is-removing')) return;
              // Сначала карточка плавно схлопывается, потом перерисовка.
              // Индекс ищем по файлу: за время анимации список мог измениться.
              wrapper.classList.add('is-removing');
              setTimeout(() => {
                  const index = selectedFiles.indexOf(file);
                  if (index !== -1) selectedFiles.splice(index, 1);
                  previewCache.delete(file);
                  updateFileInput();
                  renderPreviews();
              }, 200);
          });

          wrapper.append(img, removeBtn);
          preview.appendChild(wrapper);
          previewNodes.set(file, wrapper);

          const dataUrl = await getPreview(file);
          if (dataUrl) {
              img.src = dataUrl;
          }

          // Класс на следующем кадре, чтобы переход появления проигрался
          requestAnimationFrame(() => wrapper.classList.add('loaded'));
      }

      updateFileLabel();
      submitBtn.disabled = selectedFiles.length === 0 || uploading;
  }

  // Подпись зоны показывает, сколько выбрано и на какой объём
  function updateFileLabel() {
      if (!fileLabelText) return;
      if (!selectedFiles.length) {
          fileLabelText.textContent = defaultLabelText;
          return;
      }
      const totalMb =
          selectedFiles.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024;
      fileLabelText.textContent =
          `Выбрано: ${selectedFiles.length}, ${totalMb.toFixed(1)} МБ`;
  }

  // Превью кодируется один раз на файл; добавление/удаление других
  // файлов больше не перегоняет весь список через canvas заново.
  function getPreview(file) {
      if (!previewCache.has(file)) {
          previewCache.set(file, createPreview(file));
      }
      return previewCache.get(file);
  }

  function createPreview(file) {
      return new Promise(resolve => {
          if (!file.type.startsWith('image/')) {
              resolve('');
              return;
          }
          const img = new Image();
          const reader = new FileReader();
          // Битый файл резолвится плейсхолдером, а не вечным await
          const fail = () => resolve('');
          reader.onerror = fail;
          img.onerror = fail;
          reader.onload = e => {
              img.onload = () => {
                  const canvas = document.createElement('canvas');
                  const ctx = canvas.getContext('2d');
                  canvas.width = 200;
                  canvas.height = 120;
                  // cover-кроп вместо растягивания - портреты не плющит
                  const scale = Math.max(200 / img.width, 120 / img.height);
                  const width = img.width * scale;
                  const height = img.height * scale;
                  ctx.drawImage(img, (200 - width) / 2, (120 - height) / 2, width, height);
                  resolve(canvas.toDataURL('image/webp', 0.6));
              };
              img.src = e.target.result;
          };
          reader.readAsDataURL(file);
      });
  }

  function setPreviewState(file, state) {
      const wrapper = previewNodes.get(file);
      if (!wrapper) return;
      wrapper.classList.remove('is-uploading', 'is-done', 'is-duplicate', 'is-error');
      if (state) {
          wrapper.classList.add(`is-${state}`);
      }
  }

  function setUploadStatus(message, kind) {
      if (!statusBox) return;
      statusBox.textContent = message;
      statusBox.className = message ? `alert alert-${kind || 'info'}` : '';
      statusBox.hidden = !message;
  }

  // Файлы уходят последовательно, по одному запросу на файл -
  // виден прогресс, обрыв не теряет весь пакет, ретрай не дублирует
  // уже загруженное (сервер отсекает дубликаты по хешу).
  async function handleFormSubmit(e) {
      e.preventDefault();
      if (!selectedFiles.length || uploading) return;

      uploading = true;
      submitBtn.disabled = true;
      submitBtn.classList.add('is-loading');
      preview.classList.add('is-busy');
      setUploadStatus('', '');

      const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;
      const total = selectedFiles.length;
      const failedFiles = [];
      const failedMessages = [];
      let uploadedCount = 0;
      let duplicateCount = 0;
      let redirectUrl = '/';

      for (let i = 0; i < total; i++) {
          const file = selectedFiles[i];
          submitBtn.textContent = `Загружаем ${i + 1} из ${total}...`;
          setPreviewState(file, 'uploading');

          try {
              const formData = new FormData();
              formData.append('files', file);
              const response = await fetch(form.action, {
                  method: 'POST',
                  headers: {
                      'X-CSRFToken': csrfToken,
                      'X-Requested-With': 'XMLHttpRequest',
                  },
                  body: formData,
              });

              // Истёкшая сессия отвечает HTML-редиректом на логин -
              // отправляем пользователя туда вместо SyntaxError из json().
              const contentType = response.headers.get('content-type') || '';
              if (response.redirected || !contentType.includes('application/json')) {
                  window.location.href = response.url || form.action;
                  return;
              }

              const result = await response.json();
              if (response.ok && result.success) {
                  redirectUrl = result.redirect_url || redirectUrl;
                  if (result.duplicates && result.duplicates.length) {
                      duplicateCount += 1;
                      setPreviewState(file, 'duplicate');
                  } else {
                      uploadedCount += 1;
                      setPreviewState(file, 'done');
                  }
              } else {
                  const detail =
                      (result.errors && result.errors[0]) || result.error || 'ошибка загрузки';
                  failedFiles.push(file);
                  failedMessages.push(detail);
                  setPreviewState(file, 'error');
              }
          } catch (error) {
              failedFiles.push(file);
              failedMessages.push(`${file.name}: сеть недоступна или сервер не ответил`);
              setPreviewState(file, 'error');
          }
      }

      uploading = false;
      preview.classList.remove('is-busy');

      if (!failedFiles.length) {
          // Спиннер остаётся до ухода со страницы - редирект уже запущен
          window.location.href = redirectUrl;
          return;
      }
      submitBtn.classList.remove('is-loading');

      selectedFiles = failedFiles;
      updateFileInput();
      // Перерендер, чтобы кнопки удаления ссылались на актуальные индексы
      await renderPreviews();
      failedFiles.forEach(file => setPreviewState(file, 'error'));

      const summary = [];
      if (uploadedCount) summary.push(`загружено: ${uploadedCount}`);
      if (duplicateCount) summary.push(`дубликатов пропущено: ${duplicateCount}`);
      summary.push(`с ошибкой: ${failedFiles.length}`);
      setUploadStatus(
          `Готово не всё (${summary.join(', ')}). ${failedMessages.join(' ')}`,
          'danger'
      );

      submitBtn.disabled = false;
      submitBtn.textContent = `Повторить (${failedFiles.length})`;
  }
}

// Эффекты по мотивам React Bits (reactbits.dev), переписанные без React и GSAP

const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');

// Split Text + Variable Proximity: буквы имени въезжают из-под маски,
// а рядом с курсором становятся жирнее (вариативная ось wght у Geist).
function initWordmark() {
  const wordmark = document.querySelector('.wordmark');
  const source = wordmark && wordmark.querySelector('.wordmark-text');
  if (!source) return;

  const FROM = 500;
  const TO = 800;
  const RADIUS = 220;
  const letters = [];
  const label = source.textContent.trim();
  source.textContent = '';
  wordmark.setAttribute('aria-label', label);

  label.split(' ').forEach((word, wordIndex) => {
    if (wordIndex) source.append(' ');
    const wordEl = document.createElement('span');
    wordEl.className = 'wordmark-word';
    wordEl.setAttribute('aria-hidden', 'true');
    word.split('').forEach(char => {
      const letter = document.createElement('span');
      letter.className = 'wordmark-letter';
      letter.textContent = char;
      letter.style.setProperty('--i', String(letters.length));
      wordEl.appendChild(letter);
      letters.push(letter);
    });
    source.appendChild(wordEl);
  });

  if (!finePointer.matches) return;

  let pointer = null;
  let scheduled = false;

  const update = () => {
    scheduled = false;
    letters.forEach(letter => {
      let weight = FROM;
      if (pointer) {
        const rect = letter.getBoundingClientRect();
        const distance = Math.hypot(
          pointer.x - (rect.left + rect.width / 2),
          pointer.y - (rect.top + rect.height / 2)
        );
        // Гауссов спад: плавный пик у курсора без резкой границы радиуса
        const strength = Math.exp(-((distance / (RADIUS / 2)) ** 2) / 2);
        weight = FROM + (TO - FROM) * strength;
      }
      letter.style.fontVariationSettings = `'wght' ${weight.toFixed(0)}`;
    });
  };

  window.addEventListener('pointermove', e => {
    pointer = { x: e.clientX, y: e.clientY };
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(update);
    }
  }, { passive: true });

  document.documentElement.addEventListener('pointerleave', () => {
    pointer = null;
    requestAnimationFrame(update);
  });
}

// Target Cursor: над фото курсор становится рамкой автофокуса,
// четыре уголка защёлкиваются на снимке. Только мышь, только сетка.
function initTargetCursor() {
  const gallery = document.getElementById('gallery');
  if (!gallery || !finePointer.matches) return;

  const CORNER = 14;
  const INSET = 6; // уголки чуть снаружи снимка
  const SPIN_MS = 2400;

  const root = document.createElement('div');
  root.className = 'target-cursor';
  root.setAttribute('aria-hidden', 'true');
  const dot = document.createElement('span');
  dot.className = 'target-cursor-dot';
  const corners = ['tl', 'tr', 'br', 'bl'].map(name => {
    const corner = document.createElement('span');
    corner.className = `target-cursor-corner target-cursor-corner--${name}`;
    root.appendChild(corner);
    return corner;
  });
  root.appendChild(dot);
  document.body.appendChild(root);
  gallery.classList.add('has-target-cursor');

  const mouse = { x: -100, y: -100 };
  const pos = { x: -100, y: -100 };
  const cornerPos = corners.map(() => ({ x: -100, y: -100, r: 0 }));
  // Углы уголков по кругу: в покое рамка крутится вокруг точки
  const idleAngles = [225, 315, 45, 135];
  const idleRadius = CORNER * 1.4;
  let target = null;
  let visible = false;
  let running = false;
  let spin = 0;
  let last = performance.now();

  const lerp = (a, b, t) => a + (b - a) * t;

  function frame(now) {
    const dt = Math.min(64, now - last);
    last = now;
    const follow = 1 - Math.pow(0.001, dt / 120);
    pos.x = lerp(pos.x, mouse.x, follow);
    pos.y = lerp(pos.y, mouse.y, follow);
    dot.style.transform = `translate(${pos.x}px, ${pos.y}px)`;

    if (target && !target.isConnected) target = null;
    if (!reduceMotion.matches && !target) spin = (spin + (dt / SPIN_MS) * 360) % 360;

    let goals;
    if (target) {
      const rect = target.getBoundingClientRect();
      // Лёгкий параллакс: рамка чуть тянется за курсором внутри снимка
      const px = (pos.x - (rect.left + rect.width / 2)) * 0.03;
      const py = (pos.y - (rect.top + rect.height / 2)) * 0.03;
      goals = [
        { x: rect.left - INSET, y: rect.top - INSET },
        { x: rect.right + INSET - CORNER, y: rect.top - INSET },
        { x: rect.right + INSET - CORNER, y: rect.bottom + INSET - CORNER },
        { x: rect.left - INSET, y: rect.bottom + INSET - CORNER },
      ].map(g => ({ x: g.x + px, y: g.y + py, r: 0 }));
    } else {
      goals = idleAngles.map(angle => {
        const a = ((angle + spin) * Math.PI) / 180;
        return {
          x: pos.x + Math.cos(a) * idleRadius - CORNER / 2,
          y: pos.y + Math.sin(a) * idleRadius - CORNER / 2,
          r: spin,
        };
      });
    }

    const snap = 1 - Math.pow(0.001, dt / (target ? 160 : 60));
    corners.forEach((corner, i) => {
      const c = cornerPos[i];
      c.x = lerp(c.x, goals[i].x, snap);
      c.y = lerp(c.y, goals[i].y, snap);
      // Поворот по кратчайшему пути, чтобы уголки не делали лишний оборот
      const delta = ((goals[i].r - c.r + 540) % 360) - 180;
      c.r = target ? lerp(c.r, c.r + delta, snap) : goals[i].r;
      corner.style.transform = `translate(${c.x}px, ${c.y}px) rotate(${c.r}deg)`;
    });

    if (visible) {
      requestAnimationFrame(frame);
    } else {
      running = false;
    }
  }

  function show() {
    if (!visible) {
      visible = true;
      root.classList.add('visible');
      // Курсор появляется на месте мыши, а не прилетает из угла экрана
      pos.x = mouse.x;
      pos.y = mouse.y;
      cornerPos.forEach(c => {
        c.x = mouse.x - CORNER / 2;
        c.y = mouse.y - CORNER / 2;
      });
    }
    if (!running) {
      running = true;
      last = performance.now();
      requestAnimationFrame(frame);
    }
  }

  function hide() {
    visible = false;
    target = null;
    root.classList.remove('visible', 'locked');
  }

  document.addEventListener('pointermove', e => {
    if (e.pointerType !== 'mouse') return;
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    const over = document.elementFromPoint(e.clientX, e.clientY);
    if (!over || !gallery.contains(over)) {
      hide();
      return;
    }
    const card = over.closest('.card');
    target = card || null;
    root.classList.toggle('locked', Boolean(card));
    show();
  }, { passive: true });

  // Прокрутка двигает фото под неподвижной мышью - пересчитываем цель
  window.addEventListener('scroll', () => {
    if (!visible) return;
    const over = document.elementFromPoint(mouse.x, mouse.y);
    if (!over || !gallery.contains(over)) {
      hide();
      return;
    }
    target = over.closest('.card');
    root.classList.toggle('locked', Boolean(target));
  }, { passive: true });

  document.addEventListener('pointerdown', () => root.classList.add('pressed'));
  document.addEventListener('pointerup', () => root.classList.remove('pressed'));
  document.documentElement.addEventListener('pointerleave', hide);
}

// Split Flap: механическое табло, каждый символ перелистывается
// через несколько случайных цифр к нужному.
function createSplitFlap(el, { flipMs = 70, stagger = 35, flips = 5 } = {}) {
  const DIGITS = '0123456789';
  let tiles = [];
  let current = '';
  let raf = null;

  const isFlapChar = ch => /[0-9A-Za-zА-Яа-я]/.test(ch);

  function build(text) {
    el.textContent = '';
    el.classList.add('flap');
    tiles = text.split('').map(ch => {
      if (!isFlapChar(ch)) {
        const sep = document.createElement('span');
        sep.className = 'flap-sep';
        sep.textContent = ch === ' ' ? ' ' : ch;
        el.appendChild(sep);
        return null;
      }
      const tile = document.createElement('span');
      tile.className = 'flap-tile';
      tile.innerHTML =
        '<span class="flap-half flap-top"><span class="flap-char"></span></span>' +
        '<span class="flap-half flap-bottom"><span class="flap-char"></span></span>';
      el.appendChild(tile);
      setTile(tile, ch, ch);
      return tile;
    });
  }

  function setTile(tile, top, bottom) {
    tile.querySelector('.flap-top .flap-char').textContent = top;
    tile.querySelector('.flap-bottom .flap-char').textContent = bottom;
  }

  // Один перелёт: верхняя створка со старым символом падает, нижняя с новым встаёт
  function flipTile(tile, from, to) {
    tile.querySelectorAll('.flap-leaf').forEach(leaf => leaf.remove());
    setTile(tile, to, from);
    const front = document.createElement('span');
    front.className = 'flap-half flap-leaf flap-leaf--front';
    front.innerHTML = `<span class="flap-char">${from}</span>`;
    const back = document.createElement('span');
    back.className = 'flap-half flap-leaf flap-leaf--back';
    back.innerHTML = `<span class="flap-char">${to}</span>`;
    tile.append(front, back);
    // animationend может не прийти в фоновой вкладке - страхуемся таймером
    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      if (front.isConnected) setTile(tile, to, to);
      front.remove();
      back.remove();
    };
    back.addEventListener('animationend', settle, { once: true });
    setTimeout(settle, flipMs + 40);
  }

  function set(text, { animate = true } = {}) {
    if (raf) cancelAnimationFrame(raf);
    const sameShape = text.length === current.length &&
      text.split('').every((ch, i) => isFlapChar(ch) === isFlapChar(current[i]));
    if (!sameShape) {
      build(animate ? text.replace(/[0-9]/g, '0') : text);
      if (!animate) {
        current = text;
        el.setAttribute('aria-label', text);
        return;
      }
      current = text.replace(/[0-9]/g, '0');
    }
    el.setAttribute('aria-label', text);
    el.style.setProperty('--flip-ms', `${flipMs}ms`);

    if (!animate || reduceMotion.matches) {
      text.split('').forEach((ch, i) => tiles[i] && setTile(tiles[i], ch, ch));
      current = text;
      return;
    }

    const plans = text.split('').map((to, i) => {
      const from = current[i];
      if (!tiles[i] || from === to) return null;
      const steps = Array.from({ length: flips }, () => DIGITS[Math.floor(Math.random() * 10)]);
      steps.push(to);
      return { tile: tiles[i], from, steps, start: i * stagger, step: -1 };
    }).filter(Boolean);
    current = text;
    if (!plans.length) return;

    const began = performance.now();
    const tick = now => {
      let pending = false;
      plans.forEach(plan => {
        const step = Math.floor((now - began - plan.start) / flipMs);
        if (step < 0) {
          pending = true;
          return;
        }
        if (step < plan.steps.length) pending = true;
        const index = Math.min(step, plan.steps.length - 1);
        if (index !== plan.step) {
          const from = plan.step < 0 ? plan.from : plan.steps[plan.step];
          plan.step = index;
          flipTile(plan.tile, from, plan.steps[index]);
        }
      });
      raf = pending ? requestAnimationFrame(tick) : null;
    };
    raf = requestAnimationFrame(tick);
  }

  return { set };
}

function initFlaps() {
  document.querySelectorAll('[data-split-flap]').forEach(el => {
    const flap = createSplitFlap(el, { flipMs: 90, stagger: 120, flips: 7 });
    const text = el.textContent.trim();
    flap.set(text);
  });
}

// Появление фото по мотивам Animated Content: снимок проявляется и оседает
// из лёгкого увеличения, когда доезжает до экрана
const inViewObserver = 'IntersectionObserver' in window
  ? new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('inview');
        inViewObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -40px 0px' })
  : null;

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

// Идемпотентное завершение WAAPI-анимации: finished может не резолвиться
// (фоновая вкладка, cancel) - страхуемся таймаутом, колбэк ровно один раз.
function settleAnimation(animation, timeoutMs, done) {
  let called = false;
  const once = () => {
    if (called) return;
    called = true;
    done();
  };
  if (animation && animation.finished) {
    animation.finished.then(once, once);
  }
  setTimeout(once, timeoutMs);
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function buildUrlWithQuery(basePath, params) {
  const url = new URL(basePath, window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.set(key, String(value));
  });
  return url.toString();
}
