<h1 align="center">Django Photo Gallery</h1>

<p align="center">
  <strong>Production-ready gallery on Django + PostgreSQL with image optimization, infinite scroll, and fullscreen lightbox.</strong>
</p>

<p align="center">
  <a href="https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/tgeruzov/django-photo-gallery/actions/workflows/ci.yml/badge.svg">
  </a>
  <a href="https://www.python.org/">
    <img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white">
  </a>
  <a href="https://www.djangoproject.com/">
    <img alt="Django 3.2" src="https://img.shields.io/badge/django-3.2-0C4B33?logo=django&logoColor=white">
  </a>
  <a href="LICENSE">
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-ffd43b">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#environment-variables">Environment</a> •
  <a href="#routes">Routes</a> •
  <a href="#community">Community</a>
</p>

<hr>

<h2 id="features">Features</h2>

<table>
  <tr>
    <td>Responsive masonry-style gallery</td>
    <td>Fullscreen lightbox (keyboard + mobile gestures)</td>
  </tr>
  <tr>
    <td>Infinite scroll with JSON pagination</td>
    <td>Staff-only multi-file upload</td>
  </tr>
  <tr>
    <td>Automatic optimization + thumbnails</td>
    <td>Dark/light theme toggle</td>
  </tr>
  <tr>
    <td>PostgreSQL-first backend</td>
    <td>Docker and local dev workflows</td>
  </tr>
</table>

<h2>Tech Stack</h2>

<ul>
  <li><strong>Backend:</strong> Django 3.2</li>
  <li><strong>Database:</strong> PostgreSQL 16 (Docker image: <code>postgres:16-alpine</code>)</li>
  <li><strong>Frontend:</strong> Vanilla JS, HTML, CSS</li>
  <li><strong>Image Processing:</strong> Pillow</li>
  <li><strong>Static Files:</strong> WhiteNoise</li>
  <li><strong>WSGI Server:</strong> Gunicorn</li>
</ul>

<h2 id="quick-start">Quick Start</h2>

<h3>Requirements</h3>
<ul>
  <li>Python 3.8+</li>
  <li>PostgreSQL 14+ (or Docker)</li>
  <li>pip</li>
</ul>

<h3>1) Clone</h3>

<pre><code>git clone https://github.com/tgeruzov/django-photo-gallery.git
cd django-photo-gallery</code></pre>

<h3>2) Create .env</h3>

<pre><code># Linux / Mac
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env</code></pre>

<h3>3) Run with Docker (recommended)</h3>

<pre><code>docker compose up --build</code></pre>

<p>Open: <a href="http://localhost:8000">http://localhost:8000</a></p>

<h3>4) Run locally (without Docker)</h3>

<pre><code>python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver</code></pre>

<h2 id="environment-variables">Environment Variables</h2>

<p>Use <code>.env.example</code> as template:</p>

<p>
  <code>DEBUG</code>,
  <code>SECRET_KEY</code>,
  <code>ALLOWED_HOSTS</code>,
  <code>DB_NAME</code>,
  <code>DB_USER</code>,
  <code>DB_PASSWORD</code>,
  <code>DB_HOST</code>,
  <code>DB_PORT</code>,
  <code>MAX_UPLOAD_SIZE_MB</code>,
  <code>MAX_IMAGE_PIXELS</code>,
  <code>MAX_JSON_PAGE_SIZE</code>,
  <code>DELETE_ORIGINAL_AFTER_OPTIMIZE</code>
</p>

<h2 id="routes">Main Routes</h2>

<ul>
  <li><code>/</code> - gallery index</li>
  <li><code>/upload/</code> - multi-file upload page (staff only)</li>
  <li><code>/all_photos.json</code> - paginated JSON endpoint</li>
  <li><code>/admin/</code> - Django admin</li>
</ul>

<h2>Project Structure</h2>

<pre><code>django-photo-gallery/
├── config/
├── gallery/
├── static/
├── .github/workflows/
├── manage.py
├── docker-compose.yml
└── requirements.txt</code></pre>

<h2>Production Notes</h2>

<ul>
  <li>Set <code>DEBUG=False</code></li>
  <li>Configure <code>ALLOWED_HOSTS</code></li>
  <li>Use strong <code>SECRET_KEY</code></li>
  <li>Inject PostgreSQL credentials via environment</li>
  <li>Run <code>python manage.py collectstatic</code></li>
  <li>Set media storage + backup policy</li>
</ul>

<h2 id="community">Community</h2>

<ul>
  <li><a href="CONTRIBUTING.md">Contributing Guide</a></li>
  <li><a href="SECURITY.md">Security Policy</a></li>
  <li><a href="CODE_OF_CONDUCT.md">Code of Conduct</a></li>
</ul>

<h2>License</h2>

<p>Distributed under MIT License. See <a href="LICENSE">LICENSE</a>.</p>
