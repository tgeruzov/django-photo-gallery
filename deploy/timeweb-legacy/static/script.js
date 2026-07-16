document.addEventListener('DOMContentLoaded', function () {
  setupThemeSwitcher();
  initHeaderBehavior();
  initAlerts();
  initGallery();
  initUploadForm();
});

// U4/UX15: сообщения закрываются крестиком и сами исчезают через 6 секунд
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

function initHeaderBehavior() {
  const topbar = document.querySelector('.topbar');
  const scrollTopBtn = document.querySelector('.scroll-top');

  // Шапка sticky и живёт в потоке — разделитель появляется только
  // после начала скролла; заодно ведём прогресс-волосок и кнопку «наверх».
  const syncScroll = () => {
    const y = window.scrollY;
    if (topbar) {
      topbar.classList.toggle('is-scrolled', y > 4);
    }
    const max = document.documentElement.scrollHeight - window.innerHeight;
    document.documentElement.style.setProperty(
      '--scroll-progress',
      max > 0 ? String(Math.min(1, y / max)) : '0'
    );
    if (scrollTopBtn) {
      scrollTopBtn.classList.toggle('visible', y > 1200);
    }
  };
  window.addEventListener('scroll', syncScroll, { passive: true });
  syncScroll();

  if (scrollTopBtn) {
    scrollTopBtn.addEventListener('click', () => {
      const reduceMotion =
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
    });
  }
}

function initGallery() {
  const gallery = document.getElementById('gallery');
  if (!gallery) return;

  const cardRevealer = initLazyLoad(gallery);
  const feed = setupInfiniteScroll(gallery, cardRevealer);
  initCardTilt(gallery);
  initLightbox(gallery, feed);
}

// 3D-наклон карточки за курсором + позиция блика. Один делегированный
// слушатель на галерею; углы уходят в CSS-переменные (применяет CSS).
function initCardTilt(gallery) {
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!finePointer.matches || reduceMotion.matches) return;

  const MAX_DEG = 3.2;

  const resetTilt = (card) => {
    card.style.removeProperty('--rx');
    card.style.removeProperty('--ry');
  };

  gallery.addEventListener('pointermove', (e) => {
    const card = e.target.closest('.card');
    if (!card || card.classList.contains('card-empty')) return;
    const rect = card.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    card.style.setProperty('--px', px.toFixed(3));
    card.style.setProperty('--py', py.toFixed(3));
    card.style.setProperty('--rx', `${((px - 0.5) * MAX_DEG).toFixed(2)}deg`);
    card.style.setProperty('--ry', `${((0.5 - py) * MAX_DEG).toFixed(2)}deg`);
  });

  gallery.addEventListener('pointerout', (e) => {
    const card = e.target.closest('.card');
    if (card && !card.contains(e.relatedTarget)) {
      resetTilt(card);
    }
  });

  // Перед zoom-полётом в лайтбокс карточка выравнивается,
  // чтобы FLIP мерил ровный прямоугольник
  gallery.addEventListener('click', (e) => {
    const card = e.target.closest('.card');
    if (card) resetTilt(card);
  }, true);
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
      const applyTheme = () => {
          root.classList.toggle('light');
          const isLight = root.classList.contains('light');
          localStorage.setItem('darkMode', !isLight);
          syncThemeButtonState();
      };

      const reduceMotion =
          window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!document.startViewTransition || reduceMotion) {
          applyTheme();
          return;
      }

      // Новая тема «разливается» кругом от кнопки-переключателя.
      // Класс theme-switching отключает дефолтный кросс-фейд только
      // на время этого перехода (см. CSS), навигационный — не трогает.
      const rect = themeBtn.getBoundingClientRect();
      const x = rect.left + rect.width / 2;
      const y = rect.top + rect.height / 2;
      const radius = Math.hypot(
          Math.max(x, window.innerWidth - x),
          Math.max(y, window.innerHeight - y)
      );

      root.classList.add('theme-switching');
      const transition = document.startViewTransition(applyTheme);
      transition.ready
          .then(() => {
              root.animate(
                  {
                      clipPath: [
                          `circle(0px at ${x}px ${y}px)`,
                          `circle(${radius}px at ${x}px ${y}px)`,
                      ],
                  },
                  {
                      duration: 450,
                      easing: 'ease-in-out',
                      pseudoElement: '::view-transition-new(root)',
                  }
              );
          })
          .catch(() => {}); // переход мог быть пропущен (фоновая вкладка)
      transition.finished.finally(() => {
          root.classList.remove('theme-switching');
      });
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

  const reduceMotion =
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => {
        // UX9: пачка карточек появляется каскадом, а не одним миганием
        const visible = entries.filter(entry => entry.isIntersecting);
        visible.forEach((entry, index) => {
          observer.unobserve(entry.target);
          if (reduceMotion) {
            revealCard(entry.target);
          } else {
            setTimeout(() => revealCard(entry.target), index * 40);
          }
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
          el: img, // источник/цель zoom-полёта (как в галерее iPhone)
      }))
      .filter(photo => photo.url && photo.full_url);
  }

  function updateCounter() {
    if (!counter) return;
    counter.textContent = currentIndex >= 0 && allPhotos.length
      ? `${currentIndex + 1} / ${allPhotos.length}`
      : '';
  }

  // Ambient-свечение: средний цвет снимка (по миниатюре из кэша браузера)
  // подсвечивает фон лайтбокса — фото «освещает комнату».
  const glowCache = new Map(); // url -> rgba-строка
  function applyPhotoGlow(url) {
    if (glowCache.has(url)) {
      lightbox.style.setProperty('--photo-glow', glowCache.get(url));
      return;
    }
    const probe = new Image();
    probe.onload = () => {
      let glow = 'rgba(120, 140, 160, 0.4)';
      try {
        const canvas = document.createElement('canvas');
        canvas.width = 16;
        canvas.height = 16;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(probe, 0, 0, 16, 16);
        const data = ctx.getImageData(0, 0, 16, 16).data;
        let r = 0, g = 0, b = 0;
        const count = data.length / 4;
        for (let i = 0; i < data.length; i += 4) {
          r += data[i];
          g += data[i + 1];
          b += data[i + 2];
        }
        glow = `rgba(${Math.round(r / count)}, ${Math.round(g / count)}, ${Math.round(b / count)}, 0.5)`;
      } catch (err) {
        // canvas может быть «испачкан» кросс-доменным файлом — остаётся дефолт
      }
      glowCache.set(url, glow);
      lightbox.style.setProperty('--photo-glow', glow);
    };
    probe.src = url;
  }

  function preloadNeighbors(index) {
    [index - 1, index + 1].forEach(i => {
      if (i >= 0 && i < allPhotos.length) {
        new Image().src = allPhotos[i].full_url;
      }
    });
  }

  function showPhoto(index, direction) {
    if (index < 0 || index >= allPhotos.length) return;
    currentIndex = index;
    const photo = allPhotos[index];

    // Направленный вход нового кадра: класс перевешивается с reflow,
    // чтобы анимация проигрывалась на каждом перелистывании.
    lightboxImg.classList.remove('slide-from-left', 'slide-from-right');
    if (direction) {
      void lightboxImg.offsetWidth;
      lightboxImg.classList.add(
        direction === 'next' ? 'slide-from-right' : 'slide-from-left'
      );
    }

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
    applyPhotoGlow(photo.url);
    preloadNeighbors(index);
    showSwipeHint();
  }

  // Zoom-переходы «как в галерее iPhone»: фото вылетает из своей карточки
  // и при закрытии сжимается точно обратно (FLIP через WAAPI).
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const canZoom = () =>
    typeof lightboxImg.animate === 'function' && !reduceMotion.matches;
  let closing = false;

  function finishClose() {
    if (!closing) return;
    closing = false;
    lightbox.setAttribute('aria-hidden', 'true');
    lightboxImg.removeAttribute('src');
    lightboxImg.style.opacity = '';
    // Снимаем fill:forwards прошлого полёта, чтобы следующий показ был чистым
    if (typeof lightboxImg.getAnimations === 'function') {
      lightboxImg.getAnimations().forEach(animation => animation.cancel());
    }
    currentIndex = -1;
    updateCounter();
  }

  function zoomFromCard(sourceEl) {
    if (!canZoom() || !sourceEl) return;

    const fly = () => {
      const from = sourceEl.getBoundingClientRect();
      const to = lightboxImg.getBoundingClientRect();
      if (!from.width || !to.width) return;
      const dx = from.left + from.width / 2 - (to.left + to.width / 2);
      const dy = from.top + from.height / 2 - (to.top + to.height / 2);
      const scale = from.width / to.width;

      // На время полёта фото «поднимается» из сетки — карточка пустеет
      sourceEl.style.visibility = 'hidden';
      const animation = lightboxImg.animate(
        [
          { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, borderRadius: `${12 / scale}px` },
          { transform: 'none', borderRadius: '8px' },
        ],
        { duration: 420, easing: 'cubic-bezier(0.2, 0.9, 0.25, 1)' }
      );
      settleAnimation(animation, 620, () => {
        sourceEl.style.visibility = '';
      });
    };

    // Миниатюра почти всегда уже в кэше (она на экране) — размер известен
    // синхронно; иначе прячем кадр до load, чтобы не мигнул в полный размер.
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
    if (closing) finishClose(); // предыдущее закрытие ещё летит — обрываем
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

    const sourceEl =
      currentIndex >= 0 && allPhotos[currentIndex] ? allPhotos[currentIndex].el : null;

    // Скрим и кнопки гаснут сразу; фото в это время летит в карточку
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') {
      lastFocused.focus({ preventScroll: true });
    }
    lastFocused = null;

    const hasImage = Boolean(lightboxImg.getAttribute('src'));

    if (canZoom() && hasImage && sourceEl && sourceEl.isConnected) {
      const to = sourceEl.getBoundingClientRect();
      const from = lightboxImg.getBoundingClientRect();
      const inViewport = to.width > 0 && to.bottom > 0 && to.top < window.innerHeight;
      if (inViewport && from.width > 0) {
        const dx = to.left + to.width / 2 - (from.left + from.width / 2);
        const dy = to.top + to.height / 2 - (from.top + from.height / 2);
        const scale = to.width / from.width;
        sourceEl.style.visibility = 'hidden';
        const animation = lightboxImg.animate(
          [
            { transform: 'none', borderRadius: '8px' },
            { transform: `translate(${dx}px, ${dy}px) scale(${scale})`, borderRadius: `${12 / scale}px` },
          ],
          { duration: 400, easing: 'cubic-bezier(0.3, 0.7, 0.3, 1)', fill: 'forwards' }
        );
        settleAnimation(animation, 600, () => {
          sourceEl.style.visibility = '';
          finishClose();
        });
        return;
      }
    }

    if (canZoom() && hasImage) {
      // Карточка вне экрана — мягкое сжатие с растворением
      const animation = lightboxImg.animate(
        [
          { transform: 'none', opacity: 1 },
          { transform: 'scale(0.9)', opacity: 0 },
        ],
        { duration: 220, easing: 'ease-in', fill: 'forwards' }
      );
      settleAnimation(animation, 400, finishClose);
      return;
    }

    finishClose();
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
    if (currentIndex > 0) showPhoto(currentIndex - 1, 'prev');
  }

  async function nextPhoto() {
    if (currentIndex < allPhotos.length - 1) {
      showPhoto(currentIndex + 1, 'next');
      return;
    }
    // Достигнут конец загруженного — просим ленту догрузить страницу.
    if (feed && feed.hasMore()) {
      const appended = await feed.loadMore();
      if (!lightbox.classList.contains('active')) return;
      if (appended) {
        allPhotos = getVisiblePhotos();
        if (currentIndex < allPhotos.length - 1) {
          showPhoto(currentIndex + 1, 'next');
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

  // Смена фото на тач-устройствах — интерактивным свайпом:
  // кадр следует за пальцем, отпускание листает или возвращает на место.
  setupSwipe(lightbox, lightboxImg, prevPhoto, nextPhoto, closeLightbox);
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
    // UX21: ошибка даёт явную кнопку повтора вместо «прокрутите ещё раз»
    if (state === 'error') {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'feed-retry';
      retry.textContent = 'Повторить';
      retry.addEventListener('click', () => {
        retryBlockedUntil = 0;
        loadMore();
      });
      status.append(' ');
      status.appendChild(retry);
    }
    status.hidden = state === 'idle' || message === '';
  };

  // J8: после конца ленты слушатели не должны дёргаться на каждый скролл
  let sentinelObserver = null;
  const detachFeedListeners = () => {
    if (sentinelObserver) {
      sentinelObserver.disconnect();
      sentinelObserver = null;
    }
    window.removeEventListener('scroll', maybeLoadMore);
    window.removeEventListener('resize', maybeLoadMore);
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

    // Бэкенд использует offset-пагинацию (?page=N); keyset-курсор не нужен.
    const params = { page: nextPage };

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

          // UX20: положение в ленте отражается в URL — «назад»/перезагрузка
          // возвращают к текущей странице, а не в самый верх
          const loadedPages = Math.ceil(gallery.querySelectorAll('.card').length / 12);
          if (loadedPages > 1 && 'replaceState' in history) {
            const url = new URL(window.location.href);
            url.searchParams.set('page', String(loadedPages));
            history.replaceState(history.state, '', url);
          }
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
      } else {
        detachFeedListeners();
      }
      return appended > 0;
    } catch (err) {
      retryBlockedUntil = Date.now() + 2000;
      setFeedStatus('error', 'Не удалось загрузить еще фото.');
      console.error('Ошибка загрузки:', err);
      return false;
    }
  }

  if ('IntersectionObserver' in window) {
    sentinelObserver = new IntersectionObserver((entries) => {
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

  if (hasMore) {
    maybeLoadMore();
  } else {
    detachFeedListeners();
  }

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
  const fileLabelText = form.querySelector('.file-upload-text');
  const defaultLabelText = fileLabelText ? fileLabelText.textContent : '';
  submitBtn.disabled = true;

  // UX7: файл, уроненный мимо зоны, не должен открываться браузером
  ['dragover', 'drop'].forEach(ev =>
      window.addEventListener(ev, e => e.preventDefault())
  );

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

      // J9: повторный выбор того же файла не создаёт дубликат в пакете
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

          // UX11: класс на следующем кадре, чтобы переход появления проигрался
          requestAnimationFrame(() => wrapper.classList.add('loaded'));
      }

      updateFileLabel();
      submitBtn.disabled = selectedFiles.length === 0 || uploading;
  }

  // UX19: подпись зоны показывает, сколько выбрано и на какой объём
  function updateFileLabel() {
      if (!fileLabelText) return;
      if (!selectedFiles.length) {
          fileLabelText.textContent = defaultLabelText;
          return;
      }
      const totalMb =
          selectedFiles.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024;
      fileLabelText.textContent =
          `Выбрано: ${selectedFiles.length} файл(ов) · ${totalMb.toFixed(1)} МБ`;
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
                  // J4: cover-кроп вместо растягивания — портреты не плющит
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

  // U1: файлы уходят последовательно, по одному запросу на файл —
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
          // Спиннер остаётся до ухода со страницы — редирект уже запущен
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

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

// Интерактивный свайп: тач-события приходят только с сенсорных экранов,
// поэтому отдельная проверка «мобилка или нет» не нужна.
function setupSwipe(lightbox, img, prev, next, close) {
  let startX = null;
  let startY = null;
  let axis = null; // 'x' | 'y' — фиксируется по первому движению
  let tracking = false;

  const resetDrag = () => {
      img.classList.remove('is-dragging');
      img.style.transform = '';
      img.style.opacity = '';
  };

  lightbox.addEventListener('touchstart', function(e) {
      if (e.touches.length !== 1) {
          tracking = false;
          return;
      }
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      axis = null;
      tracking = true;
  }, { passive: true });

  lightbox.addEventListener('touchmove', function(e) {
      if (!tracking) return;
      const dX = e.touches[0].clientX - startX;
      const dY = e.touches[0].clientY - startY;

      // Ось жеста определяется один раз — диагональ не даёт
      // одновременно и листать, и закрывать.
      if (!axis) {
          if (Math.abs(dX) < 8 && Math.abs(dY) < 8) return;
          axis = Math.abs(dX) > Math.abs(dY) ? 'x' : 'y';
      }
      if (axis !== 'x') return;

      // Кадр следует за пальцем и слегка тает к краям экрана.
      // Классы входной анимации снимаем: работающая CSS-анимация
      // перебивала бы inline-transform жеста.
      img.classList.remove('slide-from-left', 'slide-from-right');
      img.classList.add('is-dragging');
      img.style.transform = `translateX(${dX}px)`;
      img.style.opacity = String(
          Math.max(0.35, 1 - Math.abs(dX) / window.innerWidth)
      );
  }, { passive: true });

  lightbox.addEventListener('touchend', function(e) {
      if (!tracking) return;
      tracking = false;
      const dX = e.changedTouches[0].clientX - startX;
      const dY = e.changedTouches[0].clientY - startY;
      resetDrag();

      if (axis === 'x' && Math.abs(dX) > 60) {
          // Палец увёл кадр влево — приходит следующий, и наоборот
          if (dX > 0) prev();
          else next();
          return;
      }

      // Вертикальный жест вниз закрывает просмотр
      if (axis === 'y' && dY > 70 && typeof close === 'function') {
          close();
      }
  }, { passive: true });

  lightbox.addEventListener('touchcancel', function() {
      tracking = false;
      resetDrag();
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

  // Чип-подпись — только у снимков с настоящим названием (как в шаблоне)
  if (photo.title || photo.alt_text) {
    const label = document.createElement('span');
    label.className = 'card-label';
    label.setAttribute('aria-hidden', 'true');
    label.textContent = photoLabel;
    card.appendChild(label);
  }

  return card;
}

// Идемпотентное завершение WAAPI-анимации: finished может не резолвиться
// (фоновая вкладка, cancel) — страхуемся таймаутом, колбэк ровно один раз.
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
