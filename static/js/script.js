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

  const savedTheme = localStorage.getItem('darkMode');
  if (savedTheme === null) {
      if (window.matchMedia('(prefers-color-scheme: light)').matches) {
          document.body.classList.add('light');
      }
  } else if (savedTheme === 'false') {
      document.body.classList.add('light');
  }

  themeBtn.addEventListener('click', () => {
      document.body.classList.toggle('light');
      const isLight = document.body.classList.contains('light');
      localStorage.setItem('darkMode', !isLight);
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

  let allPhotos = [];
  let currentIndex = -1;

  // Загружаем все фото один раз
  fetch('/all_photos.json')
    .then(resp => resp.json())
    .then(data => {
        allPhotos = data.photos || [];
    })
    .catch(() => {
        // Фолбэк на видимые фото
        allPhotos = Array.from(gallery.querySelectorAll('.card img')).map(img => ({
            url: img.src,
            full_url: img.getAttribute('data-full'),
            title: img.alt
        }));
    });

  function showPhoto(index) {
    if (index < 0 || index >= allPhotos.length) return;
    currentIndex = index;
    lightboxImg.src = allPhotos[index].full_url;
    lightbox.classList.add('active');
    showSwipeHint();
  }

  gallery.addEventListener('click', function(e) {
    const img = e.target.closest('.card img');
    if (img) {
        const fullUrl = img.getAttribute('data-full');
        const index = allPhotos.findIndex(photo => photo.full_url === fullUrl);
        if (index !== -1) showPhoto(index);
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
  if (window.innerWidth <= 600) {
    setupSwipe(lightbox, prevPhoto, nextPhoto);
  }

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
        const data = await response.json();
        
        if (data.photos && data.photos.length) {
            data.photos.forEach(photo => {
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `<img loading="lazy" src="${photo.url}" alt="${photo.title}" data-full="${photo.full_url}" />`;
                gallery.appendChild(card);
                if (observer) observer.observe(card);
            });
            page++;
            hasMore = data.has_next;
        } else {
            hasMore = false;
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
          
          const removeBtn = document.createElement('div');
          removeBtn.className = 'remove-preview';
          removeBtn.innerHTML = '×';
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
          
          if (result.success) {
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
      if (e.touches.length === 1) startX = e.touches[0].clientX;
  });
  
  lightbox.addEventListener('touchend', function(e) {
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