document.addEventListener('DOMContentLoaded', function () {
  setupThemeSwitcher();
  initHeaderBehavior();
  initGallery();
  initUploadForm();
});

function initHeaderBehavior() {
  const header = document.querySelector('header');
  if (!header) return;

  // C1: offset контента считается от реальной высоты шапки —
  // длинный hero-текст больше не уводит контент под неё.
  if ('ResizeObserver' in window) {
    new ResizeObserver((entries) => {
      const height = entries[0].target.offsetHeight;
      document.documentElement.style.setProperty('--header-offset', `${height}px`);
    }).observe(header);
  }

  // UX18: компактная шапка при скролле — фото получают больше экрана
  const syncCompact = () => {
    document.documentElement.classList.toggle('header-compact', window.scrollY > 60);
  };
  window.addEventListener('scroll', syncCompact, { passive: true });
  syncCompact();
}

function initGallery() {
  const gallery = document.getElementById('gallery');
  if (!gallery) return;

  const cardRevealer = initLazyLoad(gallery);
  const feed = setupInfiniteScroll(gallery, cardRevealer);
  initLightbox(gallery, feed);
}

function setupThemeSwitcher() {
  const themeBtn = document.querySelector('.theme-toggle');
  if (!themeBtn) return;

  // Начальная тема применяется инлайн-скриптом в <head> (класс на <html>),
  // чтобы light-пользователь не видел вспышку тёмной темы.
  const root = document.documentElement;

  const syncThemeButtonState = () => {
      const isLight = root.classList.contains('light');
      themeBtn.setAttribute('aria-pressed', String(isLight));
      themeBtn.setAttribute('aria-label', isLight ? 'Переключить на темную тему' : 'Переключить на светлую тему');
  };

  syncThemeButtonState();

  themeBtn.addEventListener('click', () => {
      root.classList.toggle('light');
      const isLight = root.classList.contains('light');
      localStorage.setItem('darkMode', !isLight);
      syncThemeButtonState();
  });
}

function initLazyLoad(container) {
  const revealCard = (card) => {
    if (!card || card.classList.contains('loaded')) return;

    const image = card.querySelector('img');
    const markLoaded = () => {
      requestAnimationFrame(() => {
        card.classList.add('loaded');
      });
    };

    if (!image || image.complete) {
      markLoaded();
      return;
    }

    const onDone = () => {
      image.removeEventListener('load', onDone);
      image.removeEventListener('error', onDone);
      markLoaded();
    };

    image.addEventListener('load', onDone, { once: true });
    image.addEventListener('error', onDone, { once: true });
  };

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          revealCard(entry.target);
          observer.unobserve(entry.target);
        });
      }, { rootMargin: '0px 0px 160px 0px', threshold: 0.01 })
    : null;

  const api = {
    observe(card) {
      if (!card || card.dataset.revealObserved === 'true') return;
      card.dataset.revealObserved = 'true';

      if (!observer) {
        revealCard(card);
        return;
      }

      observer.observe(card);
    },
    disconnect() {
      if (observer) {
        observer.disconnect();
      }
    },
  };

  container.querySelectorAll('.card:not(.loaded)').forEach(api.observe);
  return api;
}

function initLightbox(gallery, feed) {
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = lightbox ? lightbox.querySelector('img') : null;
  if (!lightbox || !lightboxImg || !gallery) return;

  // P2: лайтбокс работает по уже загруженным карточкам и догружает
  // следующую страницу ленты по необходимости — без выкачивания всей
  // библиотеки метаданных при первом клике.
  let allPhotos = [];
  let currentIndex = -1;
  let lastFocused = null;

  const closeBtn = lightbox.querySelector('.lightbox-close');
  const prevBtn = lightbox.querySelector('.lightbox-prev');
  const nextBtn = lightbox.querySelector('.lightbox-next');
  const counter = lightbox.querySelector('.lightbox-counter');

  function getVisiblePhotos() {
    return Array.from(gallery.querySelectorAll('.card img'))
      .map(img => ({
          url: img.src,
          full_url: img.getAttribute('data-full'),
          title: img.alt || '',
      }))
      .filter(photo => photo.url && photo.full_url);
  }

  function updateCounter() {
    if (!counter) return;
    counter.textContent = currentIndex >= 0 && allPhotos.length
      ? `${currentIndex + 1} / ${allPhotos.length}`
      : '';
  }

  function preloadNeighbors(index) {
    [index - 1, index + 1].forEach(i => {
      if (i >= 0 && i < allPhotos.length) {
        new Image().src = allPhotos[i].full_url;
      }
    });
  }

  function showPhoto(index) {
    if (index < 0 || index >= allPhotos.length) return;
    currentIndex = index;
    const photo = allPhotos[index];

    // Blur-up: мгновенно показываем миниатюру из кэша,
    // полную версию подменяем по её загрузке.
    lightboxImg.classList.add('is-loading');
    lightboxImg.src = photo.url;
    lightboxImg.alt = photo.title || 'Увеличенное изображение';

    const full = new Image();
    full.onload = () => {
      if (currentIndex !== index) return;
      lightboxImg.src = photo.full_url;
      lightboxImg.classList.remove('is-loading');
    };
    full.onerror = () => {
      if (currentIndex === index) lightboxImg.classList.remove('is-loading');
    };
    full.src = photo.full_url;

    updateCounter();
    preloadNeighbors(index);
    showSwipeHint();
  }

  function openLightbox(index) {
    lastFocused = document.activeElement;
    lightbox.classList.add('active');
    lightbox.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    showPhoto(index);
    if (closeBtn) closeBtn.focus();
  }

  function closeLightbox() {
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus();
    }
    lastFocused = null;
    lightbox.setAttribute('aria-hidden', 'true');
    lightboxImg.removeAttribute('src');
    currentIndex = -1;
    updateCounter();
  }

  function openFromImage(img) {
    const fullUrl = img ? img.getAttribute('data-full') : '';
    if (!fullUrl) return;

    allPhotos = getVisiblePhotos();
    const index = allPhotos.findIndex(photo => photo.full_url === fullUrl);
    if (index === -1) return;
    openLightbox(index);
  }

  gallery.addEventListener('click', function(e) {
    const card = e.target.closest('.card');
    if (!card || !gallery.contains(card)) return;

    const img = card.querySelector('img');
    if (img) {
        openFromImage(img);
    }
  });

  function prevPhoto() {
    if (currentIndex > 0) showPhoto(currentIndex - 1);
  }

  async function nextPhoto() {
    if (currentIndex < allPhotos.length - 1) {
      showPhoto(currentIndex + 1);
      return;
    }
    // Достигнут конец загруженного — просим ленту догрузить страницу.
    if (feed && feed.hasMore()) {
      const appended = await feed.loadMore();
      if (!lightbox.classList.contains('active')) return;
      if (appended) {
        allPhotos = getVisiblePhotos();
        if (currentIndex < allPhotos.length - 1) {
          showPhoto(currentIndex + 1);
        } else {
          updateCounter();
        }
      }
    }
  }

  closeBtn && closeBtn.addEventListener('click', e => { e.stopPropagation(); closeLightbox(); });
  prevBtn && prevBtn.addEventListener('click', e => { e.stopPropagation(); prevPhoto(); });
  nextBtn && nextBtn.addEventListener('click', e => { e.stopPropagation(); nextPhoto(); });

  // Закрытие по клику на фон
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  // Управление клавиатурой
  document.addEventListener('keydown', (e) => {
    if (!lightbox.classList.contains('active')) return;
    if (e.key === 'ArrowLeft') prevPhoto();
    if (e.key === 'ArrowRight') nextPhoto();
    if (e.key === 'Escape') closeLightbox();
  });

  // Focus trap: Tab не покидает модальный диалог
  lightbox.addEventListener('keydown', (e) => {
    if (e.key !== 'Tab') return;
    const focusable = Array.from(lightbox.querySelectorAll('button'))
      .filter(el => el.offsetParent !== null);
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

  // Свайпы на мобильных
  setupSwipe(lightbox, prevPhoto, nextPhoto, closeLightbox);

  // Клики по картинке на мобильных
  lightboxImg.addEventListener('click', function(e) {
    if (window.innerWidth > 600) return;
    const rect = lightboxImg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (x < rect.width / 2) {
      prevPhoto();
    } else {
      nextPhoto();
    }
  });
}

function setupInfiniteScroll(gallery, cardRevealer) {
  const sentinel = document.getElementById('gallery-sentinel');
  const status = document.getElementById('gallery-feed-status');
  if (!sentinel) {
    return { loadMore: () => Promise.resolve(false), hasMore: () => false };
  }

  let inflight = null;
  let nextPage = parsePositiveInt(sentinel.dataset.currentPage, 1) + 1;
  let hasMore = sentinel.dataset.hasNext === 'true';
  let retryBlockedUntil = 0;

  const maybeLoadMore = () => {
    if (!hasMore || inflight) return;
    const rect = sentinel.getBoundingClientRect();
    if (rect.top <= window.innerHeight + 500) {
      loadMore();
    }
  };

  const setFeedStatus = (state, message = '') => {
    if (!status) return;
    status.dataset.state = state;
    status.textContent = message;
    status.hidden = state === 'idle' || message === '';
  };

  // Возвращает промис с true, если новые карточки добавлены —
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
    setFeedStatus('loading', 'Загружаем еще фото...');

    // Keyset-курсор от последней карточки (P8); page — фолбэк,
    // если карточек с id нет.
    const cards = gallery.querySelectorAll('.card[data-id]');
    const lastId = cards.length ? cards[cards.length - 1].dataset.id : null;
    const params = lastId ? { after: lastId } : { page: nextPage };

    try {
      const response = await fetch(buildUrlWithQuery(window.location.href, params), {
        headers: {
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();

      const photos = Array.isArray(data.photos) ? data.photos : [];
      let appended = 0;
      if (photos.length) {
        const fragment = document.createDocumentFragment();
        const newCards = [];

        photos.forEach(photo => {
          const card = createGalleryCard(photo);
          if (!card) return;
          newCards.push(card);
          fragment.appendChild(card);
        });

        if (newCards.length) {
          gallery.appendChild(fragment);
          newCards.forEach(card => cardRevealer.observe(card));
          appended = newCards.length;
        }
      }

      hasMore = Boolean(data.has_next);
      if (data.page !== undefined) {
        const apiPage = parsePositiveInt(data.page, nextPage);
        nextPage = apiPage + 1;
        sentinel.dataset.currentPage = String(apiPage);
      }
      sentinel.dataset.hasNext = String(hasMore);
      setFeedStatus('idle');

      if (hasMore) {
        requestAnimationFrame(maybeLoadMore);
      }
      return appended > 0;
    } catch (err) {
      retryBlockedUntil = Date.now() + 2000;
      setFeedStatus('error', 'Не удалось загрузить еще фото. Прокрутите страницу еще раз.');
      console.error('Ошибка загрузки:', err);
      return false;
    }
  }

  if ('IntersectionObserver' in window) {
    const sentinelObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          loadMore();
        }
      });
    }, { rootMargin: '0px 0px 500px 0px' });

    sentinelObserver.observe(sentinel);
  } else {
    window.addEventListener('scroll', maybeLoadMore, { passive: true });
  }

  window.addEventListener('resize', maybeLoadMore, { passive: true });
  maybeLoadMore();

  return { loadMore, hasMore: () => hasMore };
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
  const previewCache = new Map(); // file -> Promise<dataURL> (J2: не перекодируем повторно)
  const previewNodes = new Map(); // file -> wrapper element
  submitBtn.disabled = true;

  fileInput.addEventListener('change', handleFileSelect);
  form.addEventListener('submit', handleFormSubmit);

  // Drag and drop
  const dropZone = fileInput.closest('.file-upload-wrapper');
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
      // S14: лимит приходит с сервера через data-атрибут, не хардкодится
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

      selectedFiles = selectedFiles.concat(validFiles);
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
              if (uploading) return;
              selectedFiles.splice(i, 1);
              previewCache.delete(file);
              updateFileInput();
              renderPreviews();
          });

          wrapper.append(img, removeBtn);
          preview.appendChild(wrapper);
          previewNodes.set(file, wrapper);

          const dataUrl = await getPreview(file);
          if (dataUrl) {
              img.src = dataUrl;
          }

          wrapper.classList.add('loaded');
      }

      submitBtn.disabled = selectedFiles.length === 0 || uploading;
  }

  // J2: превью кодируется один раз на файл; добавление/удаление других
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
          // J1: битый файл резолвится плейсхолдером, а не вечным await
          const fail = () => resolve('');
          reader.onerror = fail;
          img.onerror = fail;
          reader.onload = e => {
              img.onload = () => {
                  const canvas = document.createElement('canvas');
                  const ctx = canvas.getContext('2d');
                  canvas.width = 200;
                  canvas.height = 120;
                  ctx.drawImage(img, 0, 0, 200, 120);
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

  // U1: файлы уходят последовательно, по одному запросу на файл —
  // виден прогресс, обрыв не теряет весь пакет, ретрай не дублирует
  // уже загруженное (сервер отсекает дубликаты по хешу).
  async function handleFormSubmit(e) {
      e.preventDefault();
      if (!selectedFiles.length || uploading) return;

      uploading = true;
      submitBtn.disabled = true;
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

              // J3: истёкшая сессия отвечает HTML-редиректом на логин —
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
          window.location.href = redirectUrl;
          return;
      }

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

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function setupSwipe(lightbox, prev, next, close) {
  let startX = null;
  let startY = null;

  lightbox.addEventListener('touchstart', function(e) {
      if (window.innerWidth > 600) return;
      if (e.touches.length === 1) {
          startX = e.touches[0].clientX;
          startY = e.touches[0].clientY;
      }
  }, { passive: true });

  lightbox.addEventListener('touchend', function(e) {
      if (window.innerWidth > 600) return;
      if (startX === null || startY === null) return;
      const dX = e.changedTouches[0].clientX - startX;
      const dY = e.changedTouches[0].clientY - startY;
      startX = null;
      startY = null;

      // Листаем только когда горизонталь доминирует —
      // диагональный жест больше не перелистывает случайно.
      if (Math.abs(dX) > 50 && Math.abs(dX) > Math.abs(dY)) {
          if (dX > 0) prev();
          else next();
          return;
      }

      // Свайп вниз закрывает просмотр
      if (dY > 70 && Math.abs(dY) > Math.abs(dX) && typeof close === 'function') {
          close();
      }
  }, { passive: true });
}

function showSwipeHint() {
  const hint = document.querySelector('.lightbox-hint');
  if (!hint) return;

  if (window.innerWidth > 600) {
      hint.style.display = 'none';
      return;
  }

  if (!sessionStorage.getItem('hintShown')) {
      hint.style.display = 'block';
      setTimeout(() => {
          hint.style.opacity = '0';
      }, 2000);
      sessionStorage.setItem('hintShown', 'true');
  }
}

function createGalleryCard(photo) {
  if (!photo || !photo.url || !photo.full_url) return null;
  const photoLabel = photo.alt_text || photo.title || 'Фотография';

  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'card';
  if (photo.id !== undefined && photo.id !== null) {
    card.dataset.id = String(photo.id);
  }
  card.setAttribute('aria-label', `Открыть фото: ${photoLabel}`);

  const img = document.createElement('img');
  img.loading = 'lazy';
  img.decoding = 'async';
  img.src = photo.url;
  img.alt = photoLabel;
  img.dataset.full = photo.full_url;

  const width = parsePositiveInt(photo.width, 0);
  const height = parsePositiveInt(photo.height, 0);
  if (width > 0 && height > 0) {
    img.width = width;
    img.height = height;
  }

  card.appendChild(img);
  return card;
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
