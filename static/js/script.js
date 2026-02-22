document.addEventListener('DOMContentLoaded', function () {
  setupThemeSwitcher();
  const gallery = document.getElementById('gallery');
  if (gallery) {
      const lazyLoader = initLazyLoad(gallery);
      setupInfiniteScroll(gallery, lazyLoader);
  }
  initLightbox();
  initUploadForm();
});

function setupThemeSwitcher() {
  const themeBtn = document.querySelector('.theme-toggle');
  if (!themeBtn) return;

  const syncThemeButtonState = () => {
      const isLight = document.body.classList.contains('light');
      themeBtn.setAttribute('aria-pressed', String(isLight));
      themeBtn.setAttribute('aria-label', isLight ? 'Переключить на темную тему' : 'Переключить на светлую тему');
  };

  const savedTheme = localStorage.getItem('darkMode');
  if (savedTheme === null) {
      if (window.matchMedia('(prefers-color-scheme: light)').matches) {
          document.body.classList.add('light');
      }
  } else if (savedTheme === 'false') {
      document.body.classList.add('light');
  }
  syncThemeButtonState();

  themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('light');
      const isLight = document.body.classList.contains('light');
      localStorage.setItem('darkMode', !isLight);
      syncThemeButtonState();
  });
}

function initLazyLoad(container) {
  const cards = container.querySelectorAll('.card:not(.loaded)');
  if (cards.length === 0) return null;
  
  const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
          if (entry.isIntersecting) {
              setTimeout(() => {
                  entry.target.classList.add('loaded');
              }, 50);
              observer.unobserve(entry.target);
          }
      });
  }, { rootMargin: '0px 0px 100px 0px', threshold: 0.01 });
  
  cards.forEach(card => observer.observe(card));
  return observer;
}

function initLightbox() {
  const lightbox = document.getElementById('lightbox');
  const lightboxImg = lightbox ? lightbox.querySelector('img') : null;
  const gallery = document.getElementById('gallery');
  if (!lightbox || !lightboxImg || !gallery) return;

  const allPhotosUrl = gallery.dataset.allPhotosUrl || '/all_photos.json';
  let allPhotos = getVisiblePhotos();
  let allPhotosPromise = null;
  let currentIndex = -1;

  function getVisiblePhotos() {
    return Array.from(gallery.querySelectorAll('.card img'))
      .map(img => ({
          url: img.src,
          full_url: img.getAttribute('data-full'),
          title: img.alt || '',
      }))
      .filter(photo => photo.url && photo.full_url);
  }

  function ensureAllPhotosLoaded() {
    if (allPhotosPromise) return allPhotosPromise;

    allPhotosPromise = fetchAllPhotos(allPhotosUrl)
      .then(photos => {
          if (Array.isArray(photos) && photos.length) {
              allPhotos = photos;
          }
          return allPhotos;
      })
      .catch(() => {
          // Фолбэк на локально видимые фото и возможность повторной попытки позже
          allPhotos = getVisiblePhotos();
          allPhotosPromise = null;
          return allPhotos;
      });

    return allPhotosPromise;
  }

  function showPhoto(index) {
    if (index < 0 || index >= allPhotos.length) return;
    currentIndex = index;
    lightboxImg.src = allPhotos[index].full_url;
    lightboxImg.alt = allPhotos[index].title || 'Увеличенное изображение';
    lightbox.classList.add('active');
    showSwipeHint();
  }

  function openFromImage(img) {
    const fullUrl = img ? img.getAttribute('data-full') : '';
    if (!fullUrl) return;

    if (!allPhotos.length) {
        allPhotos = getVisiblePhotos();
    }

    let index = allPhotos.findIndex(photo => photo.full_url === fullUrl);
    if (index === -1) {
        allPhotos = getVisiblePhotos();
        index = allPhotos.findIndex(photo => photo.full_url === fullUrl);
    }

    if (index === -1) return;
    showPhoto(index);

    ensureAllPhotosLoaded().then(photos => {
        if (!lightbox.classList.contains('active')) return;
        const refreshedIndex = photos.findIndex(photo => photo.full_url === fullUrl);
        if (refreshedIndex !== -1) {
            currentIndex = refreshedIndex;
        }
    });
  }

  gallery.addEventListener('click', function(e) {
    const card = e.target.closest('.card');
    if (!card || !gallery.contains(card)) return;

    const img = card.querySelector('img');
    if (img) {
        openFromImage(img);
    }
  });

  function closeLightbox() {
    lightbox.classList.remove('active');
    lightboxImg.src = '';
    currentIndex = -1;
  }

  function prevPhoto() {
    if (currentIndex > 0) showPhoto(currentIndex - 1);
  }

  function nextPhoto() {
    if (currentIndex < allPhotos.length - 1) showPhoto(currentIndex + 1);
  }

  // Кнопки навигации
  const prevBtn = lightbox.querySelector('.lightbox-prev');
  const nextBtn = lightbox.querySelector('.lightbox-next');
  
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

  // Свайпы на мобильных
  setupSwipe(lightbox, prevPhoto, nextPhoto);

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

function setupInfiniteScroll(gallery, observer) {
  let loading = false;
  let page = 2;
  let hasMore = true;

  async function loadMore() {
    if (loading || !hasMore) return;
    loading = true;
    
    try {
        const response = await fetch(`?page=${page}`, {
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        
        if (Array.isArray(data.photos) && data.photos.length) {
            data.photos.forEach(photo => {
                const card = createGalleryCard(photo);
                if (!card) return;
                gallery.appendChild(card);
                if (observer) observer.observe(card);
            });
        }
        hasMore = Boolean(data.has_next);
        if (hasMore) {
            const apiPage = Number(data.page);
            page = Number.isFinite(apiPage) && apiPage > 0 ? apiPage + 1 : page + 1;
        }
    } catch (err) {
        console.error('Ошибка загрузки:', err);
    } finally {
        loading = false;
    }
  }

  window.addEventListener('scroll', () => {
    const scrollPos = window.innerHeight + window.pageYOffset;
    const threshold = document.body.offsetHeight * 0.8;
    if (scrollPos >= threshold) {
        loadMore();
    }
  });
}

function initUploadForm() {
  const form = document.getElementById('upload-form');
  const fileInput = document.getElementById('id_files');
  const preview = document.getElementById('preview-container');
  const submitBtn = document.getElementById('submit-btn');
  
  if (!form || !fileInput || !preview || !submitBtn) return;

  let selectedFiles = [];
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
      const validFiles = files.filter(f => f.size <= 100 * 1024 * 1024);
      const oversized = files.filter(f => f.size > 100 * 1024 * 1024);
      
      if (oversized.length) {
          alert(`Слишком большие файлы:\n${oversized.map(f => `${f.name} (${Math.round(f.size/1024/1024)}MB)`).join('\n')}`);
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
              selectedFiles.splice(i, 1);
              updateFileInput();
              renderPreviews();
          });
          
          wrapper.append(img, removeBtn);
          preview.appendChild(wrapper);
          
          if (file.type.startsWith('image/')) {
              img.src = await createPreview(file);
          }
          
          wrapper.classList.add('loaded');
      }
      
      submitBtn.disabled = selectedFiles.length === 0;
  }

  function createPreview(file) {
      return new Promise(resolve => {
          const img = new Image();
          const reader = new FileReader();
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

  async function handleFormSubmit(e) {
      e.preventDefault();
      if (!selectedFiles.length) return;
      
      submitBtn.disabled = true;
      submitBtn.textContent = 'Загружаем...';
      
      try {
          const formData = new FormData(form);
          const response = await fetch(form.action, {
              method: 'POST',
              headers: {
                  'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value,
                  'X-Requested-With': 'XMLHttpRequest',
              },
              body: formData,
          });
          
          const result = await response.json();
          
          if (response.ok && result.success) {
              selectedFiles = [];
              updateFileInput();
              preview.innerHTML = '';
              window.location.href = result.redirect_url;
          } else {
              throw new Error(result.error || 'Ошибка загрузки');
          }
      } catch (error) {
          alert('Ошибка: ' + error.message);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Опубликовать';
      }
  }
}

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

function setupSwipe(lightbox, prev, next) {
  let startX = null;
  
  lightbox.addEventListener('touchstart', function(e) {
      if (window.innerWidth > 600) return;
      if (e.touches.length === 1) startX = e.touches[0].clientX;
  });
  
  lightbox.addEventListener('touchend', function(e) {
      if (window.innerWidth > 600) return;
      if (startX === null) return;
      const endX = e.changedTouches[0].clientX;
      const diff = endX - startX;
      
      if (Math.abs(diff) > 50) {
          if (diff > 0) prev();
          else next();
      }
      startX = null;
  });
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

  const card = document.createElement('button');
  card.type = 'button';
  card.className = 'card';
  card.setAttribute('aria-label', `Открыть фото: ${photo.title || 'Без названия'}`);

  const img = document.createElement('img');
  img.loading = 'lazy';
  img.src = photo.url;
  img.alt = photo.title || '';
  img.dataset.full = photo.full_url;

  card.appendChild(img);
  return card;
}

function buildUrlWithQuery(basePath, params) {
  const url = new URL(basePath, window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.set(key, String(value));
  });
  return url.toString();
}

async function fetchAllPhotos(basePath) {
  const allPhotos = [];
  let page = 1;
  let hasNext = true;
  const pageSize = 100;

  while (hasNext) {
    const url = buildUrlWithQuery(basePath, { page, page_size: pageSize });
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Не удалось получить фото: ${response.status}`);
    }

    const data = await response.json();
    if (Array.isArray(data.photos)) {
      allPhotos.push(...data.photos.filter(photo => photo && photo.full_url && photo.url));
    }

    hasNext = Boolean(data.has_next);
    page += 1;

    if (page > 1000) {
      console.warn('Остановлена загрузка lightbox: слишком много страниц');
      break;
    }
  }

  return allPhotos;
}
