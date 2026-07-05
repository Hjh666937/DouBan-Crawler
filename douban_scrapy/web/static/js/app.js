let currentGenre = '';
let currentPage = 1;
let currentSearch = '';
const PAGE_SIZE = 24;

async function api(url, options = {}) {
    const resp = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    const data = await resp.json();
    if (!resp.ok && !data.ok) {
        throw new Error(data.message || data.error || '请求失败');
    }
    return data;
}

function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show' + (isError ? ' error' : '');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function setCount(n) {
    document.getElementById('targetCount').value = n;
}

async function loadStats() {
    const stats = await api('/api/stats');
    document.getElementById('statMovies').textContent = stats.movies_in_csv;
    document.getElementById('statReviewRows').textContent = stats.review_rows;
    document.getElementById('statComments').textContent = stats.comments_movies_done;
    document.getElementById('statGenres').textContent = stats.genres_count;

    const dot = document.getElementById('statusDot');
    const msg = document.getElementById('taskMessage');
    if (stats.crawl_running) {
        dot.className = 'status-dot running';
        msg.textContent = '爬虫运行中，可随时停止并更换 Cookie';
        document.getElementById('btnStart').disabled = true;
        document.getElementById('btnStop').disabled = false;
        document.getElementById('btnStopSave').disabled = false;
    } else {
        dot.className = 'status-dot idle';
        msg.textContent = stats.cookie_configured ? '系统空闲，可开始爬取' : '未配置 Cookie';
        document.getElementById('btnStart').disabled = false;
        document.getElementById('btnStop').disabled = true;
        document.getElementById('btnStopSave').disabled = true;
    }
}

async function loadGenres() {
    const data = await api('/api/genres');
    const bar = document.getElementById('genreBar');
    bar.innerHTML = '<button class="genre-chip active" data-genre="">全部</button>';

    data.genres.forEach(item => {
        const btn = document.createElement('button');
        btn.className = 'genre-chip';
        btn.dataset.genre = item.name;
        btn.textContent = `${item.name} (${item.count})`;
        btn.onclick = () => selectGenre(item.name, btn);
        bar.appendChild(btn);
    });

    bar.querySelector('[data-genre=""]').onclick = (e) => selectGenre('', e.target);
}

function selectGenre(genre, btn) {
    currentGenre = genre;
    currentPage = 1;
    document.querySelectorAll('.genre-chip').forEach(chip => chip.classList.remove('active'));
    btn.classList.add('active');
    loadMovies();
}

async function loadMovies() {
    currentSearch = document.getElementById('searchInput').value.trim();
    const params = new URLSearchParams({
        page: currentPage,
        page_size: PAGE_SIZE,
        genre: currentGenre,
        search: currentSearch,
    });

    const data = await api(`/api/movies?${params}`);
    document.getElementById('resultCount').textContent = `共 ${data.total} 部电影`;

    const grid = document.getElementById('movieGrid');
    if (!data.movies.length) {
        grid.innerHTML = '<div class="empty-state">暂无电影数据，请先开始爬取</div>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    grid.innerHTML = data.movies.map(movie => `
        <article class="movie-card" onclick="openDetail('${movie.movie_id}')">
            <div class="poster-wrap">
                ${movie.poster_url
                    ? `<img src="${movie.poster_url}" alt="${escapeHtml(movie.name)}" loading="lazy"
                           onerror="this.parentElement.innerHTML='<div class=poster-placeholder>🎬</div>'">`
                    : '<div class="poster-placeholder">🎬</div>'}
                ${movie.douban_rating > 0 ? `<span class="rating-badge">${movie.douban_rating}</span>` : ''}
                ${movie.has_comments ? '<span class="comment-badge">有短评</span>' : ''}
            </div>
            <div class="card-info">
                <h3>${escapeHtml(movie.name)}</h3>
                <div class="genre-tags">
                    ${movie.genre.map(g => `<span class="genre-tag">${escapeHtml(g)}</span>`).join('')}
                </div>
            </div>
        </article>
    `).join('');

    renderPagination(data.total, data.page, data.page_size);
}

function renderPagination(total, page, pageSize) {
    const totalPages = Math.ceil(total / pageSize);
    const container = document.getElementById('pagination');
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    let html = `<button class="page-btn" ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">上一页</button>`;
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    for (let i = start; i <= end; i++) {
        html += `<button class="page-btn ${i === page ? 'active' : ''}" onclick="goPage(${i})">${i}</button>`;
    }
    html += `<button class="page-btn" ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页</button>`;
    container.innerHTML = html;
}

function goPage(page) {
    currentPage = page;
    loadMovies();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function openDetail(movieId) {
    const overlay = document.getElementById('modalOverlay');
    const body = document.getElementById('modalBody');
    overlay.classList.add('open');
    body.innerHTML = '加载中...';

    try {
        const movie = await api(`/api/movies/${movieId}`);
        const genres = Array.isArray(movie.genre) ? movie.genre.join(' / ') : movie.genre;

        body.innerHTML = `
            <div class="detail-header">
                ${movie.poster_url
                    ? `<img class="detail-poster" src="${movie.poster_url}" alt="${escapeHtml(movie.name)}">`
                    : '<div class="detail-poster"></div>'}
                <div class="detail-meta">
                    <h2>${escapeHtml(movie.name)}</h2>
                    <p>导演：${escapeHtml(movie.director || '未知')}</p>
                    <p>编剧：${escapeHtml(movie.screenwriter || '未知')}</p>
                    <p>主演：${escapeHtml((movie.actors || '').slice(0, 80))}</p>
                    <p>类型：${escapeHtml(genres || '未知')}</p>
                    <p>国家：${escapeHtml(movie.country || '未知')}</p>
                    <p>上映：${escapeHtml(movie.release_date || '未知')}</p>
                    <p>片长：${escapeHtml(movie.runtime || '未知')}</p>
                    <div class="detail-rating">${movie.douban_rating || movie.rating || '-'} 分</div>
                    <p>${movie.rating_count || 0} 人评价 · ${movie.short_comment_count || movie.short_review_count || 0} 条短评</p>
                </div>
            </div>
            <div class="detail-section">
                <h3>剧情简介</h3>
                <p class="plot-text">${escapeHtml(movie.plot || movie.summary || '暂无简介')}</p>
            </div>
            ${movie.comments && movie.comments.length ? `
            <div class="detail-section">
                <h3>热门短评 (${movie.comments.length})</h3>
                ${movie.comments.map(c => `
                    <div class="comment-item">
                        <div class="comment-head">
                            <span class="comment-user">${escapeHtml(c.nickname)}</span>
                            <span>${escapeHtml(c.comment_time)} · <span class="comment-votes">${c.helpful_votes} 有用</span></span>
                        </div>
                        <div class="comment-content">${escapeHtml(c.content)}</div>
                    </div>
                `).join('')}
            </div>` : ''}
        `;
    } catch (e) {
        body.innerHTML = `<p style="color:var(--danger)">${escapeHtml(e.message)}</p>`;
    }
}

function closeModal(event) {
    if (event && event.target !== document.getElementById('modalOverlay')) return;
    document.getElementById('modalOverlay').classList.remove('open');
}

async function startCrawl() {
    const n = parseInt(document.getElementById('targetCount').value, 10);
    try {
        const d = await api('/api/crawl', {
            method: 'POST',
            body: JSON.stringify({ target_count: n }),
        });
        showToast(d.message);
        loadStats();
        refreshLogs();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function stopCrawl() {
    try {
        const d = await api('/api/stop', { method: 'POST', body: '{}' });
        showToast(d.message);
        loadStats();
        refreshLogs();
        loadGenres();
        loadMovies();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function stopAndSaveCookie() {
    const cookie = document.getElementById('cookieInput').value.trim();
    if (!cookie) {
        showToast('请先粘贴新的 Cookie', true);
        return;
    }
    try {
        const d = await api('/api/stop', {
            method: 'POST',
            body: JSON.stringify({ cookie }),
        });
        showToast(d.message);
        loadStats();
        refreshLogs();
        loadGenres();
        loadMovies();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function refreshLogs() {
    try {
        const d = await api('/api/logs');
        const box = document.getElementById('logBox');
        if (d.logs) {
            box.textContent = d.logs;
            box.scrollTop = box.scrollHeight;
        }
    } catch (e) { /* ignore */ }
}

async function saveCookie() {
    try {
        const d = await api('/api/config/cookie', {
            method: 'POST',
            body: JSON.stringify({ cookie: document.getElementById('cookieInput').value.trim() }),
        });
        showToast(d.message);
        loadStats();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function loadCookie() {
    const d = await api('/api/config/cookie');
    document.getElementById('cookieInput').value = d.cookie || '';
}

async function loadDbConfig() {
    const d = await api('/api/config/db');
    document.getElementById('dbServer').value = d.server || 'localhost';
    document.getElementById('dbPort').value = d.port || 1433;
    document.getElementById('dbName').value = d.database || 'DoubanMovies';
    document.getElementById('dbUser').value = d.user || 'sa';
    document.getElementById('dbPassword').value = d.password || '';
    document.getElementById('dbWinAuth').checked = !!d.use_windows_auth;
}

async function saveDbConfig() {
    try {
        const d = await api('/api/config/db', {
            method: 'POST',
            body: JSON.stringify({
                server: document.getElementById('dbServer').value,
                port: parseInt(document.getElementById('dbPort').value, 10),
                database: document.getElementById('dbName').value,
                user: document.getElementById('dbUser').value,
                password: document.getElementById('dbPassword').value,
                use_windows_auth: document.getElementById('dbWinAuth').checked,
            }),
        });
        showToast(d.message);
    } catch (e) {
        showToast(e.message, true);
    }
}

async function initDb() {
    try {
        const d = await api('/api/db/init', { method: 'POST' });
        showToast(d.message);
    } catch (e) {
        showToast(e.message, true);
    }
}

async function importCsv() {
    try {
        const d = await api('/api/db/import', { method: 'POST' });
        showToast(d.message);
    } catch (e) {
        showToast(e.message, true);
    }
}

async function refreshAll() {
    await loadStats();
    await loadGenres();
    await loadMovies();
    showToast('数据已刷新');
}

loadCookie();
loadDbConfig();
loadStats();
loadGenres();
loadMovies();
setInterval(loadStats, 3000);
setInterval(refreshLogs, 2000);
setInterval(() => { loadGenres(); loadMovies(); }, 15000);
