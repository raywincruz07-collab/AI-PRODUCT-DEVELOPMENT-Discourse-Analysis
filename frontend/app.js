/* ═══════════════════════════════════════════
   Discourse Analyzer — Frontend Application
   ═══════════════════════════════════════════ */

const API = '';

// ── Chart.js Global Defaults ──
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 13;
Chart.defaults.color = '#475569';
Chart.defaults.borderColor = 'rgba(0,0,0,0.06)';

const C = {
    amber: '#2563eb',
    amberFill: 'rgba(37, 99, 235, 0.08)',
    violet: '#6366f1',
    violetFill: 'rgba(99, 102, 241, 0.08)',
    green: '#10b981',
    greenFill: 'rgba(16, 185, 129, 0.08)',
    red: '#ef4444',
    sky: '#06b6d4',
    grid: 'rgba(0,0,0,0.05)',
    tick: '#475569',
    label: '#334155',
};

const chartScaleDefaults = {
    x: {
        ticks: { color: C.tick, maxTicksLimit: 12, font: { size: 12 } },
        grid: { color: C.grid },
        border: { display: false }
    },
    y: {
        ticks: { color: C.tick, font: { size: 12 } },
        grid: { color: C.grid },
        border: { display: false }
    },
};

const barScaleDefaults = {
    x: {
        ticks: { color: C.tick, font: { size: 12 } },
        grid: { color: C.grid },
        border: { display: false }
    },
    y: {
        ticks: { color: C.tick, font: { family: "'JetBrains Mono', monospace", size: 12 } },
        grid: { display: false },
        border: { display: false }
    },
};

// ── Tab Navigation ──
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        item.classList.add('active');
        document.getElementById(item.dataset.tab).classList.add('active');

        if (item.dataset.tab === 'trends') loadTrends();
    });
});

// ── Utility ──
function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

function truncate(text, max = 320) {
    return text.length > max ? text.slice(0, max) + '…' : text;
}

// Show a window that spans all matched terms so every searched word is visible.
// Finds the earliest and latest match positions and builds a snippet covering both.
function contextSnippet(text, terms, max = 480) {
    if (!terms || !terms.length) return truncate(text, max);
    const lower = text.toLowerCase();
    let firstIdx = -1, lastIdx = -1;
    for (const t of terms) {
        if (!t) continue;
        const idx = lower.indexOf(t.toLowerCase());
        if (idx === -1) continue;
        if (firstIdx === -1 || idx < firstIdx) firstIdx = idx;
        const end = idx + t.length;
        if (end > lastIdx) lastIdx = end;
    }
    if (firstIdx === -1) return truncate(text, max);
    const start = Math.max(0, firstIdx - 60);
    const minEnd = lastIdx + 60;
    const end = Math.min(text.length, Math.max(start + max, minEnd));
    const slice = text.slice(start, end);
    const prefix = start > 0 ? '…' : '';
    const suffix = end < text.length ? '…' : '';
    return prefix + slice + suffix;
}

// Wrap each search term in <mark> after the text has been HTML-escaped.
function highlightTerms(html, terms) {
    if (!terms || !terms.length) return html;
    for (const term of terms) {
        if (!term || term.length < 2) continue;
        const safe = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        html = html.replace(new RegExp(safe, 'gi'), m => `<mark class="hl">${m}</mark>`);
    }
    return html;
}

function cleanContent(text) {
    return text
        .replace(/https?:\/\/\s*\S+/g, '')
        .replace(/#\s+(\S+)/g, '#$1')
        .replace(/[ \t]{2,}/g, ' ')
        .trim();
}

function platformClass(platform) {
    if (platform === '4chan') return 'fourchan';
    if (platform === 'truthsocial') return 'truthsocial';
    return 'mastodon';
}

function platformLabel(platform) {
    if (platform === '4chan') return '4chan';
    if (platform === 'truthsocial') return 'Truth Social';
    return 'Mastodon';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ── Stats Bar ──
async function loadStats() {
    try {
        const res = await fetch(`${API}/api/stats`);
        const stats = await res.json();
        const bar = document.getElementById('stats-bar');
        if (!stats.length) {
            bar.innerHTML = '<div class="stats-loading">Collecting data...</div>';
            return;
        }
        bar.innerHTML = stats.map(s => `
            <div class="stat-block">
                <div class="stat-platform">${platformLabel(s.platform)}</div>
                <div class="stat-numbers">
                    <div>
                        <div class="stat-value">${s.total_posts.toLocaleString()}</div>
                        <div class="stat-label">posts</div>
                    </div>
                    <div>
                        <div class="stat-value">${s.unique_authors.toLocaleString()}</div>
                        <div class="stat-label">authors</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Stats error:', e);
    }
}

// ── Post Explorer ──
let currentPage = 1;

async function searchPosts(page = 1) {
    currentPage = page;
    const keyword = document.getElementById('search-keyword').value;
    const platform = document.getElementById('search-platform').value;
    const author = document.getElementById('search-author').value;
    const start = document.getElementById('search-start').value;
    const end = document.getElementById('search-end').value;

    const params = new URLSearchParams();
    if (keyword) params.set('keyword', keyword);
    if (platform) params.set('platform', platform);
    if (author) params.set('author', author);
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    params.set('page', page);
    params.set('limit', 25);

    try {
        const res = await fetch(`${API}/api/posts?${params}`);
        const data = await res.json();
        renderPosts(data);
    } catch (e) {
        document.getElementById('posts-list').innerHTML =
            '<div class="empty-state">Error loading posts.</div>';
    }
}

function renderPosts(data) {
    const { posts, total, page, limit } = data;
    const info = document.getElementById('search-info');
    info.textContent = total > 0
        ? `${posts.length} of ${total.toLocaleString()} results — page ${page}`
        : '';

    const list = document.getElementById('posts-list');
    if (!posts.length) {
        list.innerHTML = `
            <div class="empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
                </svg>
                <p>No posts found. Try different filters or wait for data collection.</p>
            </div>`;
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    const activeTerms = (document.getElementById('search-keyword').value || '')
        .trim().split(/\s+/).filter(Boolean);

    list.innerHTML = posts.map((p, index) => {
        const raw = cleanContent(p.content_text);
        const snippet = contextSnippet(raw, activeTerms);
        const content = highlightTerms(escapeHtml(snippet), activeTerms);
        const board = p.board_or_feed ? `<span class="post-board">${escapeHtml(p.board_or_feed)}</span>` : '';
        const hasEngagement = p.likes || p.replies || p.shares;
        return `
        <div class="post-card platform-${p.platform}" style="animation-delay: ${index * 0.05}s">
            <div class="post-header">
                <div class="post-meta-left">
                    <span class="platform-badge ${platformClass(p.platform)}">${platformLabel(p.platform)}</span>
                    <span class="post-author">${escapeHtml(p.author || 'Anonymous')}</span>
                    ${board}
                </div>
                <span class="post-time">${formatDate(p.posted_at)}</span>
            </div>
            <div class="post-content">${content}</div>
            ${hasEngagement ? `
            <div class="post-footer">
                ${p.likes ? `<div class="post-stat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a2 2 0 0 1 3 1.88V5.88"/>
                    </svg>
                    <span>${p.likes.toLocaleString()}</span>
                </div>` : ''}
                ${p.replies ? `<div class="post-stat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    <span>${p.replies.toLocaleString()}</span>
                </div>` : ''}
                ${p.shares ? `<div class="post-stat">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/>
                    </svg>
                    <span>${p.shares.toLocaleString()}</span>
                </div>` : ''}
            </div>` : ''}
        </div>`;
    }).join('');

    // Pagination
    const totalPages = Math.ceil(total / limit);
    const pag = document.getElementById('pagination');
    if (totalPages <= 1) { pag.innerHTML = ''; return; }

    let html = '';
    if (page > 1) html += `<button onclick="searchPosts(${page - 1})">Prev</button>`;
    const startP = Math.max(1, page - 3);
    const endP = Math.min(totalPages, page + 3);
    for (let i = startP; i <= endP; i++) {
        html += `<button class="${i === page ? 'active-page' : ''}" onclick="searchPosts(${i})">${i}</button>`;
    }
    if (page < totalPages) html += `<button onclick="searchPosts(${page + 1})">Next</button>`;
    pag.innerHTML = html;
}

document.getElementById('search-btn').addEventListener('click', () => searchPosts(1));
document.getElementById('search-keyword').addEventListener('keypress', e => {
    if (e.key === 'Enter') searchPosts(1);
});

// ── Trend Dashboard ──
let keywordFreqChart;

async function loadVelocityAlerts() {
    const container = document.getElementById('alerts-container');
    const platform = document.getElementById('trend-platform').value;

    try {
        const params = new URLSearchParams();
        if (platform) params.set('platform', platform);

        const res = await fetch(`${API}/api/alerts/velocity?${params}`);
        const alerts = await res.json();

        if (!alerts || alerts.length === 0) {
            container.innerHTML = '<div class="alerts-empty">No keyword spikes detected in the last hour</div>';
            return;
        }

        container.innerHTML = alerts.map(a => `
            <div class="alert-card">
                <div class="alert-keyword">${escapeHtml(a.keyword)}</div>
                <div class="alert-stats">
                    <span class="spike-badge">↑ ${a.spike_ratio}×</span>
                    <span class="platform-badge ${platformClass(a.platform)}">${platformLabel(a.platform)}</span>
                </div>
                <div class="alert-meta">
                    <div>Recent: ${a.recent_count} mentions</div>
                    <div style="font-size: 0.65rem; opacity: 0.7;">
                        Detected: ${formatDate(a.first_seen_spike)} (approximate)
                    </div>
                </div>
                <div class="alert-actions">
                    <button class="btn-primary alert-btn-search" onclick="searchFromAlert('${escapeHtml(a.keyword)}')">
                        Search this keyword
                    </button>
                    <button class="btn-trace-origin" data-keyword="${escapeHtml(a.keyword)}">
                        Trace Origin →
                    </button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Velocity alerts error:', e);
        container.innerHTML = '<div class="alerts-empty">Error loading alerts</div>';
    }
}

function searchFromAlert(keyword) {
    // Switch to explorer tab
    document.querySelectorAll('.nav-item').forEach(n => {
        if (n.dataset.tab === 'explorer') {
            n.click();
        }
    });
    
    // Set keyword and trigger search
    const input = document.getElementById('search-keyword');
    if (input) {
        input.value = keyword;
        searchPosts(1);
    }
}

function getVolumeStartDate(granularity) {
    const now = new Date();
    if (granularity === 'hour') {
        // Last 24 hours only — 24 data points maximum
        now.setHours(now.getHours() - 24);
    } else if (granularity === 'day') {
        // Last 30 days only — 30 data points maximum
        now.setDate(now.getDate() - 30);
    } else if (granularity === 'week') {
        // Last 12 weeks only — 12 data points maximum
        now.setDate(now.getDate() - 84);
    }
    return now.toISOString();
}

async function loadTrends() {
    loadVelocityAlerts();
}

async function trackKeyword() {
    const keyword = document.getElementById('track-keyword').value;
    if (!keyword) return;
    const platform = document.getElementById('trend-platform').value;

    try {
        const params = new URLSearchParams({ keyword, granularity: 'day' });
        if (platform) params.set('platform', platform);

        const res = await fetch(`${API}/api/keywords/frequency?${params}`);
        const data = await res.json();

        if (keywordFreqChart) keywordFreqChart.destroy();
        keywordFreqChart = new Chart(document.getElementById('keyword-freq-chart'), {
            type: 'line',
            data: {
                labels: data.map(d => d.period),
                datasets: [{
                    label: `"${keyword}"`,
                    data: data.map(d => d.count),
                    borderColor: C.green,
                    backgroundColor: C.greenFill,
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHitRadius: 10,
                    pointHoverRadius: 4,
                    pointHoverBackgroundColor: C.green,
                }]
            },
            options: {
                responsive: true,
                interaction: { intersect: false, mode: 'index' },
                scales: chartScaleDefaults,
                plugins: {
                    legend: { labels: { color: '#334155', usePointStyle: true, pointStyle: 'circle' } },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        borderColor: 'rgba(203,213,225,0.8)',
                        borderWidth: 1,
                        titleColor: '#0f172a',
                        bodyColor: '#64748b',
                        padding: 10,
                        cornerRadius: 6,
                    }
                }
            }
        });
    } catch (e) { console.error('Keyword freq error:', e); }
}

document.getElementById('trend-refresh').addEventListener('click', loadTrends);
document.getElementById('trend-platform').addEventListener('change', loadTrends);
document.getElementById('track-btn').addEventListener('click', trackKeyword);
document.getElementById('track-keyword').addEventListener('keypress', e => {
    if (e.key === 'Enter') trackKeyword();
});

// ── Narrative Explorer ──
let cooccurrenceChart, compare4chanChart, compareTsChart, compareTruthChart;

async function analyzeNarrative() {
    const keyword = document.getElementById('narrative-keyword').value;
    if (!keyword) return;
    const platform = document.getElementById('narrative-platform').value;

    try {
        const params = new URLSearchParams({ keyword });
        if (platform) params.set('platform', platform);

        const res = await fetch(`${API}/api/narratives/cooccurrence?${params}`);
        const data = await res.json();

        document.getElementById('narrative-info').textContent =
            `${data.total_posts} posts`;

        const monoBlues = ['#1e3a8a','#1d4ed8','#2563eb','#3b82f6','#60a5fa','#93c5fd','#bfdbfe'];

        if (cooccurrenceChart) cooccurrenceChart.destroy();
        const coocCanvas = document.getElementById('cooccurrence-chart');
        cooccurrenceChart = new Chart(coocCanvas, {
            type: 'bar',
            data: {
                labels: data.co_occurring.map(d => d.keyword),
                datasets: [{
                    data: data.co_occurring.map(d => d.count),
                    backgroundColor: data.co_occurring.map((_, i) => monoBlues[i % monoBlues.length]),
                    borderRadius: 4,
                    barPercentage: 0.6,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                onClick(event, elements) {
                    if (!elements.length) return;
                    const clickedTerm = data.co_occurring[elements[0].index].keyword;
                    switchTab('explorer');
                    setTimeout(() => {
                        const input = document.getElementById('search-keyword');
                        if (input) {
                            input.value = `${keyword} ${clickedTerm}`;
                            searchPosts(1);
                        }
                    }, 100);
                },
                onHover(event, elements) {
                    if (event.native) {
                        event.native.target.style.cursor = elements.length ? 'pointer' : 'default';
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { display: true },
                        ticks: { color: '#6b7280' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#374151', autoSkip: false }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });

        const existingHint = coocCanvas.parentElement.querySelector('.cooc-hint');
        if (existingHint) existingHint.remove();
        const hint = document.createElement('p');
        hint.className = 'cooc-hint';
        hint.textContent = 'Click any term to see posts containing both keywords';
        hint.style.cssText = 'font-size:0.75rem;color:#6b7280;margin-top:8px;text-align:center;';
        coocCanvas.parentElement.appendChild(hint);
    } catch (e) { console.error('Narrative error:', e); }
}

async function compareNarratives() {
    const keyword = document.getElementById('narrative-keyword').value;
    if (!keyword) return;

    document.getElementById('compare-container').style.display = 'grid';

    try {
        const res = await fetch(`${API}/api/narratives/compare?keyword=${encodeURIComponent(keyword)}`);
        const data = await res.json();

        document.getElementById('compare-info').textContent =
            `"${keyword}" — 4chan: ${data['4chan'].total_posts} posts | Mastodon: ${data.mastodon.total_posts} posts | Truth Social: ${data.truthsocial.total_posts} posts`;

        // 4chan chart
        if (compare4chanChart) compare4chanChart.destroy();
        const chan = data['4chan'].co_occurring;
        compare4chanChart = new Chart(document.getElementById('compare-chart-4chan'), {
            type: 'bar',
            data: {
                labels: chan.map(d => d.keyword),
                datasets: [{
                    data: chan.map(d => d.count),
                    backgroundColor: C.green,
                    borderRadius: 3,
                    barThickness: 14,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                scales: barScaleDefaults,
                plugins: { legend: { display: false } }
            }
        });

        // Mastodon chart
        if (compareTsChart) compareTsChart.destroy();
        const ts = data.mastodon.co_occurring;
        compareTsChart = new Chart(document.getElementById('compare-chart-ts'), {
            type: 'bar',
            data: {
                labels: ts.map(d => d.keyword),
                datasets: [{
                    data: ts.map(d => d.count),
                    backgroundColor: C.violet,
                    borderRadius: 3,
                    barThickness: 14,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                scales: barScaleDefaults,
                plugins: { legend: { display: false } }
            }
        });

        // Truth Social chart
        if (compareTruthChart) compareTruthChart.destroy();
        const truth = data.truthsocial.co_occurring;
        compareTruthChart = new Chart(document.getElementById('compare-chart-truthsocial'), {
            type: 'bar',
            data: {
                labels: truth.map(d => d.keyword),
                datasets: [{
                    data: truth.map(d => d.count),
                    backgroundColor: C.red,
                    borderRadius: 3,
                    barThickness: 14,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                scales: barScaleDefaults,
                plugins: { legend: { display: false } }
            }
        });
    } catch (e) { console.error('Compare error:', e); }
}

document.getElementById('narrative-btn').addEventListener('click', analyzeNarrative);
document.getElementById('compare-btn').addEventListener('click', compareNarratives);
document.getElementById('narrative-keyword').addEventListener('keypress', e => {
    if (e.key === 'Enter') analyzeNarrative();
});

async function loadNarrativeDifferences() {
    const keyword = document.getElementById('diff-keyword').value;
    const start = document.getElementById('diff-start').value;
    const end = document.getElementById('diff-end').value;

    if (!keyword) {
        alert('Please enter a keyword to analyze.');
        return;
    }

    const resultsContainer = document.getElementById('narrative-difference-results');
    resultsContainer.innerHTML = `
        <div class="empty-state">
            <div class="spinner" style="margin-bottom: 1rem;"></div>
            <p>Analyzing narrative differences across platforms...</p>
        </div>
    `;

    try {
        const params = new URLSearchParams({ keyword });
        if (start) params.set('start', start);
        if (end) params.set('end', end);

        const res = await fetch(`${API}/api/narratives/differences?${params}`);
        const data = await res.json();
        renderNarrativeDifferences(data);
    } catch (e) {
        console.error('Narrative difference error:', e);
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <p style="color: var(--signal-red);">Unable to analyze narrative differences. Please try again.</p>
            </div>
        `;
    }
}

function renderNarrativeDifferences(data) {
    const container = document.getElementById('narrative-difference-results');

    if (data.status === 'Insufficient Data') {
        container.innerHTML = `
            <div class="empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p style="font-weight:500; margin-bottom:0.5rem;">Insufficient data to compare narratives reliably.</p>
                <p style="font-size:0.82rem; opacity:0.7;">${data.detail || 'Try a more widely-discussed keyword, or wait for more data to be collected.'}</p>
            </div>
        `;
        return;
    }

    const statusClass = {
        'Similar Narrative': 'status-similar',
        'Mildly Different Framing': 'status-mild',
        'Distinct Framing': 'status-distinct',
        'Potential Contradiction': 'status-contradiction'
    }[data.status] || 'status-insufficient';

    // Per-platform cards — interpretation first, keywords as supporting context
    const platformInterpMap = {};
    (data.platform_interpretations || []).forEach(pi => {
        platformInterpMap[pi.platform] = pi.interpretation;
    });

    const platformsHtml = data.platforms.map(p => {
        const interp = platformInterpMap[p.platform] || '';
        const snippetsHtml = p.snippets && p.snippets.length
            ? p.snippets.map(s => `<div class="snippet-item">${escapeHtml(truncate(s, 200))}</div>`).join('')
            : '<div class="snippet-item" style="opacity:0.5">No supporting snippets available for this platform.</div>';

        return `
            <div class="platform-diff-card">
                <h4>
                    ${platformLabel(p.platform)}
                    <span class="platform-badge ${platformClass(p.platform)}">${p.post_count.toLocaleString()} posts</span>
                </h4>

                ${interp ? `<p class="platform-interp-text">${interp}</p>` : ''}

                <div class="kw-context-label">Top associated terms</div>
                <div class="kw-chip-group">
                    ${p.top_keywords.map(kw => `<span class="kw-chip">${escapeHtml(kw)}</span>`).join('')}
                </div>

                <div class="snippet-box">
                    <span class="snippet-label">Example posts</span>
                    ${snippetsHtml}
                </div>
            </div>
        `;
    }).join('');

    const whyHtml = (data.why_this_conclusion || []).map(w => `<li>${w}</li>`).join('');

    container.innerHTML = `
        <!-- Final Observation — human-readable, prominent -->
        <div class="interp-observation">
            <div class="interp-observation-label">Final Observation</div>
            <p class="interp-observation-text">${data.final_observation || ''}</p>
        </div>

        <!-- 3. Plain-English Explanation -->
        <div class="interp-explanation">
            <div class="interp-section-label">What This Means</div>
            <p class="interp-explanation-text">${data.plain_explanation || ''}</p>
        </div>

        <!-- 4. Platform-wise interpretation + evidence -->
        <div class="interp-section-label" style="margin-top: 1.5rem; margin-bottom: 0.75rem;">Platform-wise Analysis</div>
        <div class="platform-diff-grid">
            ${platformsHtml}
        </div>

        <!-- 5. Why this conclusion was reached -->
        <div class="interp-why">
            <div class="interp-section-label">Methodology & Reasoning</div>
            <ul class="explanation-list">
                ${whyHtml}
            </ul>
        </div>
    `;
}

document.getElementById('diff-analyze-btn').addEventListener('click', loadNarrativeDifferences);
document.getElementById('diff-keyword').addEventListener('keypress', e => {
    if (e.key === 'Enter') loadNarrativeDifferences();
});


// ── Export Tool ──
let exportInitialized = false;

function initExport() {
    if (exportInitialized) return;
    
    const rangeSelect = document.getElementById('export-range');
    const downloadBtn = document.getElementById('download-btn');

    if (!rangeSelect || !downloadBtn) {
        return;
    }

    rangeSelect.addEventListener('change', function() {
        const isCustom = this.value === 'custom';
        const startDiv = document.getElementById('custom-date-start');
        const endDiv = document.getElementById('custom-date-end');
        if (startDiv) startDiv.style.display = isCustom ? 'block' : 'none';
        if (endDiv) endDiv.style.display = isCustom ? 'block' : 'none';
        
        if (!isCustom) {
            const dates = getPresetDates(this.value);
            const startInput = document.getElementById('export-start');
            const endInput = document.getElementById('export-end');
            if (startInput) startInput.value = dates.start;
            if (endInput) endInput.value = dates.end;
        }
    });

    // Default dates
    const dates = getPresetDates('today');
    const startInput = document.getElementById('export-start');
    const endInput = document.getElementById('export-end');
    if (startInput) startInput.value = dates.start;
    if (endInput) endInput.value = dates.end;

    downloadBtn.addEventListener('click', triggerExport);
    exportInitialized = true;
    console.log('Export tool ready.');
}

function getPresetDates(preset) {
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const d = new Date();
    
    if (preset === '7days') d.setDate(d.getDate() - 7);
    else if (preset === '30days') d.setDate(d.getDate() - 30);
    
    return { 
        start: d.toISOString().split('T')[0], 
        end: today 
    };
}

async function triggerExport() {
    const btn = document.getElementById('download-btn');
    const errorDiv = document.getElementById('export-error');
    const loadingDiv = document.getElementById('export-loading');
    
    if (errorDiv) errorDiv.style.display = 'none';
    if (loadingDiv) loadingDiv.style.display = 'flex';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Preparing...';
    }

    try {
        const platform = document.getElementById('export-platform').value;
        const format = document.getElementById('export-format').value;
        const start = document.getElementById('export-start').value;
        const end = document.getElementById('export-end').value;

        if (!start || !end) {
            showExportError('Select both start and end dates.');
            return;
        }

        if (new Date(start) > new Date(end)) {
            showExportError('Start date after end date.');
            return;
        }

        const params = new URLSearchParams({
            platform, format, start_date: start, end_date: end
        });

        const response = await fetch(`/api/export?${params}`);
        if (response.status === 404) {
            showExportError('No records found for these filters.');
            return;
        }
        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        const disp = response.headers.get('Content-Disposition');
        let filename = `discourse_export_${platform}_${start}_to_${end}.${format}`;
        if (disp && disp.includes('filename=')) {
            filename = disp.split('filename=')[1].replace(/['"]/g, '');
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        if (loadingDiv) loadingDiv.style.display = 'none';
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Export';
        }
    } catch (e) {
        showExportError('System error. Please try again.');
        console.error(e);
    }
}

function showExportError(msg) {
    const errorDiv = document.getElementById('export-error');
    const loadingDiv = document.getElementById('export-loading');
    const btn = document.getElementById('download-btn');
    if (errorDiv) {
        errorDiv.textContent = msg;
        errorDiv.style.display = 'block';
    }
    if (loadingDiv) loadingDiv.style.display = 'none';
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Export';
    }
}

async function submitQuestion() {
    const question = document.getElementById('qa-question').value.trim();
    const platform = document.getElementById('qa-platform').value;
    const start = document.getElementById('qa-start').value;
    const end = document.getElementById('qa-end').value;
    const resultsDiv = document.getElementById('qa-results');

    // Validate
    if (!question) {
        resultsDiv.innerHTML = `<div class="callout callout-warn">Please enter a question before submitting.</div>`;
        return;
    }

    // Show loader
    resultsDiv.innerHTML = `
        <div class="empty-state">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            <p>Searching collected posts…</p>
        </div>`;

    try {
        const response = await fetch('/api/qa/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, platform, start, end })
        });

        if (response.status === 429) {
            resultsDiv.innerHTML = `<div class="callout callout-warn">Too many requests. Please wait a moment before trying again.</div>`;
            return;
        }

        if (response.status === 400) {
            const err = await response.json();
            resultsDiv.innerHTML = `<div class="callout callout-warn">${err.detail}</div>`;
            return;
        }

        if (!response.ok) {
            resultsDiv.innerHTML = `<div class="callout callout-warn">Analysis could not be completed. Please try again.</div>`;
            return;
        }

        const data = await response.json();
        renderQAResult(data, question);

    } catch (err) {
        resultsDiv.innerHTML = `<div class="callout callout-warn">Analysis could not be completed. Please try again.</div>`;
    }
}

function renderQAResult(data, question) {
    const resultsDiv = document.getElementById('qa-results');

    // Answer badge class
    const badgeClass = data.answer === 'YES' ? 'yes' : data.answer === 'NO' ? 'no' : 'insufficient';

    // Confidence bar class
    const confClass = data.confidence <= 40 ? 'low' : data.confidence <= 70 ? 'medium' : 'high';

    // Platform badges
    const platformBadges = (data.platforms_found || []).map(p => {
        const cls = p === '4chan' ? 'fourchan' : p === 'mastodon' ? 'mastodon' : 'truthsocial';
        const label = p === 'truthsocial' ? 'Truth Social' : p;
        return `<span class="platform-badge ${cls}">${label}</span>`;
    }).join('');

    // Supporting snippets
    const snippets = (data.supporting_snippets || []).map(s => {
        const cls = s.platform === '4chan' ? 'fourchan' : s.platform === 'mastodon' ? 'mastodon' : 'truthsocial';
        const label = s.platform === 'truthsocial' ? 'Truth Social' : s.platform;
        const date = s.posted_at ? new Date(s.posted_at).toLocaleDateString() : '';
        return `
            <div class="qa-snippet">
                <div class="qa-snippet-meta">
                    <span class="platform-badge ${cls}">${label}</span>
                    <span class="post-author">${s.author || 'Anonymous'}</span>
                    <span class="post-time">${date}</span>
                </div>
                <div class="qa-snippet-content">"${s.content}"</div>
            </div>`;
    }).join('');

    const snippetsSection = data.supporting_snippets && data.supporting_snippets.length > 0
        ? `<span class="qa-evidence-label">Supporting Evidence</span>${snippets}`
        : `<div class="empty-state" style="padding: 1.5rem;">No supporting snippets available.</div>`;

    resultsDiv.innerHTML = `
        <div class="qa-result-card">
            <div class="qa-answer-header">
                <div>
                    <div style="font-size:var(--fs-xs); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.12em; color:var(--text-secondary); margin-bottom:0.5rem;">Answer</div>
                    <span class="qa-answer-badge ${badgeClass}">${data.answer}</span>
                </div>
                <div class="qa-confidence">
                    <span class="qa-confidence-label">Confidence</span>
                    <div class="qa-confidence-bar-track">
                        <div class="qa-confidence-bar-fill ${confClass}" style="width:${data.confidence}%;"></div>
                    </div>
                    <span class="qa-confidence-value">${data.confidence}%</span>
                </div>
            </div>

            <div class="qa-body">
                <div class="qa-why">${data.why}</div>

                <div class="qa-meta-row">
                    <div class="qa-meta-item">
                        <span class="qa-meta-label">Posts Analyzed</span>
                        <span class="qa-meta-value">${data.total_posts_analyzed}</span>
                    </div>
                    <div class="qa-meta-item">
                        <span class="qa-meta-label">Platforms Found</span>
                        <span style="display:flex; gap:0.4rem; flex-wrap:wrap; margin-top:0.2rem;">${platformBadges || '<span style="color:var(--text-secondary);">None</span>'}</span>
                    </div>
                </div>

                ${snippetsSection}

                <div class="qa-limitation">
                    ⚠ ${data.limitation_note}
                </div>
            </div>
        </div>

        <button class="create-report-btn" id="create-report-btn" onclick="generateReport()">
            &#128196; Create Journalist Report
        </button>
        <div id="report-output"></div>`;

    // Store QA result + filters so the report uses the exact same verdict
    window._qaContext = { question, platform: document.getElementById('qa-platform').value, start: document.getElementById('qa-start').value, end: document.getElementById('qa-end').value, qa_answer: data };
}

async function generateReport() {
    const btn = document.getElementById('create-report-btn');
    const reportDiv = document.getElementById('report-output');
    if (!btn || !reportDiv) return;

    const ctx = window._qaContext || {};
    if (!ctx.question) return;

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Generating report…';
    reportDiv.innerHTML = '';

    try {
        const response = await fetch('/api/qa/create-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: ctx.question, platform: ctx.platform || null, start: ctx.start || null, end: ctx.end || null, qa_answer: ctx.qa_answer || null })
        });

        if (response.status === 429) {
            reportDiv.innerHTML = `<div class="callout callout-warn">Too many requests. Please wait before generating another report.</div>`;
            btn.disabled = false;
            btn.innerHTML = '&#128196; Create Journalist Report';
            return;
        }

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            reportDiv.innerHTML = `<div class="callout callout-warn">${err.detail || 'Report generation failed. Please try again.'}</div>`;
            btn.disabled = false;
            btn.innerHTML = '&#128196; Create Journalist Report';
            return;
        }

        const report = await response.json();
        downloadReport(report);

        // Show success status, no dashboard display
        reportDiv.innerHTML = `<div style="display:flex;align-items:center;gap:0.6rem;margin-top:0.75rem;font-size:var(--fs-sm);color:var(--signal-green);">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/><path d="M5 8l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Report opened — in the print dialog choose <strong>Save as PDF</strong>.
        </div>`;
        btn.disabled = false;
        btn.innerHTML = '&#128196; Open Report Again';
        btn.onclick = () => downloadReport(report);

    } catch (err) {
        reportDiv.innerHTML = `<div class="callout callout-warn">Report generation failed. Please try again.</div>`;
        btn.disabled = false;
        btn.innerHTML = '&#128196; Create Journalist Report';
    }
}

function downloadReport(r) {
    const platLabel = p => p === 'truthsocial' ? 'Truth Social' : p === '4chan' ? '4chan' : p.charAt(0).toUpperCase() + p.slice(1);
    const esc = s => (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    const verdictColor = r.verdict === 'YES' ? '#16a34a' : r.verdict === 'NO' ? '#dc2626' : '#d97706';
    const verdictBg    = r.verdict === 'YES' ? '#f0fdf4' : r.verdict === 'NO' ? '#fef2f2' : '#fffbeb';
    const verdictBorder= r.verdict === 'YES' ? '#86efac' : r.verdict === 'NO' ? '#fca5a5' : '#fde68a';

    // Verdict-supporting snippets
    const qaSnippetsHtml = (r.qa_supporting_snippets || []).map(s => {
        const plat = platLabel(s.platform || '');
        const cls  = (s.platform || '') === '4chan' ? 'badge-4chan' : (s.platform || '') === 'mastodon' ? 'badge-mastodon' : 'badge-truth';
        const date = s.posted_at ? new Date(s.posted_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}) : '';
        return `<div class="snippet">
            <div class="snippet-meta"><span class="badge ${cls}">${esc(plat)}</span><strong>${esc(s.author||'Anonymous')}</strong><span class="muted">${date}</span></div>
            <blockquote>${esc(s.content||'')}</blockquote>
        </div>`;
    }).join('');

    // Key points
    const pointsHtml = (r.key_discussion_points || []).map(p => `<li>${esc(p)}</li>`).join('');

    // Keywords
    const kwHtml = (r.related_keywords || []).map(k => `<span class="kw">${esc(k)}</span>`).join('');

    // Platform table
    const platRowsHtml = Object.entries(r.platform_breakdown || {}).map(([plat, d]) =>
        `<tr><td>${esc(platLabel(plat))}</td><td>${d.post_count}</td><td>${d.unique_authors}</td></tr>`
    ).join('');

    // Platform observations
    const platObsHtml = r.platform_observations
        ? `<p class="obs">${esc(r.platform_observations)}</p>` : '';

    // Evidence posts grouped by platform
    let evHtml = '';
    let currentPlat = null;
    (r.evidence_posts || []).forEach(p => {
        const lbl = platLabel(p.platform||'');
        const cls = (p.platform||'') === '4chan' ? 'badge-4chan' : (p.platform||'') === 'mastodon' ? 'badge-mastodon' : 'badge-truth';
        const board = p.board_or_feed ? ` <span class="muted">· ${esc(p.board_or_feed)}</span>` : '';
        if (lbl !== currentPlat) {
            if (currentPlat !== null) evHtml += '</div>';
            evHtml += `<h3>${esc(lbl)}</h3><div class="ev-group">`;
            currentPlat = lbl;
        }
        evHtml += `<div class="snippet">
            <div class="snippet-meta"><span class="badge ${cls}">${esc(lbl)}</span><strong>${esc(p.author)}</strong><span class="muted">${esc(p.posted_at)}${board}</span></div>
            <blockquote>${esc(p.content)}</blockquote>
        </div>`;
    });
    if (currentPlat !== null) evHtml += '</div>';

    const coveragePlatforms = (r.platforms_covered || []).map(platLabel).join(', ');
    const dateStr = new Date().toLocaleDateString('en-GB',{day:'numeric',month:'long',year:'numeric'});

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${esc(r.title)}</title>
<style>
  @page { margin: 2cm 2.2cm; size: A4; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Georgia', serif; font-size: 10.5pt; color: #1e293b; line-height: 1.65; background: #fff; }
  .page-header { border-bottom: 3px solid #2563eb; padding-bottom: 14px; margin-bottom: 22px; }
  .report-label { font-family: Arial, sans-serif; font-size: 8pt; text-transform: uppercase; letter-spacing: .12em; color: #64748b; margin-bottom: 6px; }
  h1 { font-size: 18pt; color: #0f172a; line-height: 1.3; margin-bottom: 8px; }
  .meta { font-family: Arial, sans-serif; font-size: 8.5pt; color: #64748b; display: flex; flex-wrap: wrap; gap: 16px; }
  .meta span { display: flex; align-items: center; gap: 4px; }
  h2 { font-family: Arial, sans-serif; font-size: 12pt; font-weight: 700; color: #1e3a5f; border-left: 4px solid #2563eb; padding-left: 10px; margin: 22px 0 10px; page-break-after: avoid; }
  h3 { font-family: Arial, sans-serif; font-size: 10pt; font-weight: 600; color: #334155; margin: 14px 0 6px; }
  p { margin-bottom: 10px; }
  .verdict-box { border: 1.5px solid ${verdictBorder}; background: ${verdictBg}; border-radius: 8px; padding: 16px 20px; margin-bottom: 14px; page-break-inside: avoid; }
  .verdict-line { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; }
  .verdict-badge { font-family: Arial, sans-serif; font-size: 14pt; font-weight: 800; color: ${verdictColor}; letter-spacing: .04em; }
  .conf-bar-track { flex: 1; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
  .conf-bar-fill { height: 100%; background: ${verdictColor}; border-radius: 4px; width: ${r.verdict_confidence}%; }
  .conf-label { font-family: Arial, sans-serif; font-size: 8pt; color: #64748b; white-space: nowrap; }
  .verdict-why { font-size: 10pt; color: #334155; line-height: 1.6; }
  .section { margin-bottom: 18px; }
  .summary-text { font-size: 10.5pt; line-height: 1.7; }
  ul.points { padding-left: 18px; }
  ul.points li { margin-bottom: 6px; font-size: 10pt; line-height: 1.6; }
  .kw-cloud { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .kw { font-family: 'Courier New', monospace; font-size: 8.5pt; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 12px; padding: 2px 9px; color: #475569; }
  table { width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 9pt; margin-top: 10px; }
  th { background: #f1f5f9; border: 1px solid #e2e8f0; padding: 7px 10px; text-align: left; color: #334155; }
  td { border: 1px solid #e2e8f0; padding: 7px 10px; }
  tr:nth-child(even) td { background: #f8fafc; }
  .obs { font-size: 9.5pt; color: #475569; margin-top: 10px; font-style: italic; }
  .snippet { background: #f8fafc; border-left: 3px solid #2563eb; padding: 10px 14px; margin-bottom: 10px; border-radius: 0 6px 6px 0; page-break-inside: avoid; }
  .snippet-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-family: Arial, sans-serif; font-size: 8.5pt; flex-wrap: wrap; }
  .muted { color: #94a3b8; }
  blockquote { font-size: 9.5pt; color: #334155; line-height: 1.6; font-style: italic; margin: 0; }
  .badge { font-family: Arial, sans-serif; font-size: 7.5pt; font-weight: 700; padding: 2px 7px; border-radius: 4px; }
  .badge-mastodon { background: #ede9fe; color: #5b21b6; }
  .badge-4chan    { background: #dcfce7; color: #14532d; }
  .badge-truth    { background: #fee2e2; color: #991b1b; }
  .investigate-text { font-size: 10pt; color: #334155; line-height: 1.7; background: #f0fdf4; border-left: 4px solid #16a34a; padding: 12px 16px; border-radius: 0 6px 6px 0; }
  .interp-text { font-size: 10pt; color: #334155; line-height: 1.7; background: #eff6ff; border-left: 4px solid #2563eb; padding: 12px 16px; border-radius: 0 6px 6px 0; }
  .disclaimer { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 12px 16px; font-size: 8.5pt; color: #78350f; line-height: 1.6; margin-top: 24px; }
  .print-hint { font-family: Arial, sans-serif; font-size: 9pt; background: #eff6ff; border: 1px solid #bfdbfe; padding: 10px 16px; border-radius: 6px; margin-bottom: 20px; color: #1e40af; }
  @media print { .print-hint { display: none; } body { font-size: 10pt; } }
  .ev-group { margin-bottom: 6px; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }
</style>
</head>
<body>

<div class="print-hint">&#128438; To save as PDF: press <strong>Ctrl+P</strong> (or Cmd+P on Mac) → select <strong>Save as PDF</strong> → click Save.</div>

<div class="page-header">
  <div class="report-label">Discourse Analyzer &nbsp;·&nbsp; Public Discourse Report</div>
  <h1>${esc(r.title)}</h1>
  <div class="meta">
    <span>&#128197; ${dateStr}</span>
    <span>&#10067; ${esc(r.focus_question)}</span>
    <span>&#128202; ${r.total_posts_analyzed} posts &nbsp;·&nbsp; ${esc(coveragePlatforms)}</span>
  </div>
</div>

<h2>Verdict</h2>
<div class="verdict-box">
  <div class="verdict-line">
    <span class="verdict-badge">${esc(r.verdict)}</span>
    <div class="conf-bar-track"><div class="conf-bar-fill"></div></div>
    <span class="conf-label">Confidence: ${r.verdict_confidence}%</span>
  </div>
  <div class="verdict-why">${esc(r.verdict_explanation)}</div>
</div>
${qaSnippetsHtml ? `<h3>Posts supporting this verdict</h3>${qaSnippetsHtml}` : ''}

<hr>

${r.narrative_overview ? `<h2>Narrative Overview</h2><div class="section"><p class="summary-text">${esc(r.narrative_overview)}</p></div><hr>` : ''}

<h2>Executive Summary</h2>
<div class="section"><p class="summary-text">${esc(r.executive_summary)}</p></div>

<hr>

${pointsHtml ? `<h2>Key Discussion Points</h2><div class="section"><ul class="points">${pointsHtml}</ul></div><hr>` : ''}

${kwHtml ? `<h2>Related Terms in Discourse</h2><div class="section"><div class="kw-cloud">${kwHtml}</div></div><hr>` : ''}

<h2>Platform Coverage</h2>
<div class="section">
  <table>
    <thead><tr><th>Platform</th><th>Posts</th><th>Unique Authors</th></tr></thead>
    <tbody>${platRowsHtml}</tbody>
  </table>
  ${platObsHtml}
</div>

<hr>

${evHtml ? `<h2>Evidence Posts</h2><div class="section">${evHtml}</div><hr>` : ''}

${r.what_to_investigate ? `<h2>What Journalists Should Investigate</h2><div class="section"><div class="investigate-text">${esc(r.what_to_investigate)}</div></div><hr>` : ''}

<h2>Interpretation</h2>
<div class="section"><div class="interp-text">${esc(r.interpretation)}</div></div>

<div class="disclaimer">&#9888;&nbsp; <strong>Disclaimer:</strong> ${esc(r.disclaimer)}</div>

</body>
</html>`;

    const w = window.open('', '_blank');
    w.document.write(html);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 600);
}

// ── Init ──
function mainInit() {
    try {
        console.log('Main Init started...');
        loadStats();
        loadVelocityAlerts();
        // Only load Trends if it's the active tab, or on initial load to populate charts
        if (document.getElementById('trends').classList.contains('active')) {
            loadTrends();
        } else {
            // Background load to ensure charts are ready
            loadTrends();
        }
        searchPosts(1);
        initExport();
        setInterval(loadStats, 60000);
        setInterval(loadVelocityAlerts, 300000); // 5 min
        console.log('Main Init completed.');
    } catch (e) {
        console.error('Main Init failed:', e);
    }
}

// Global click listener fallback for dynamically added or late-binding buttons
document.addEventListener('click', (e) => {
    if (e.target.closest('#download-btn')) {
        console.log('Global click detected on download-btn');
        if (!exportInitialized) initExport();
        triggerExport();
    }
});

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        mainInit();
        
        // QA Event listeners
        const qaSubmit = document.getElementById('qa-submit');
        if (qaSubmit) {
            qaSubmit.addEventListener('click', submitQuestion);
        }

        const qaQuestion = document.getElementById('qa-question');
        if (qaQuestion) {
            qaQuestion.addEventListener('keydown', function(e) {
                // Enter alone submits, Shift+Enter adds new line
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    submitQuestion();
                }
            });
        }

        // Origin Tracer Event listeners
        const traceBtn = document.getElementById('origin-trace-btn');
        if (traceBtn) {
            traceBtn.addEventListener('click', function() {
                const keyword = document.getElementById('origin-keyword').value.trim();
                if (keyword) traceOrigin(keyword);
            });
        }

        const originInput = document.getElementById('origin-keyword');
        if (originInput) {
            originInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    const keyword = this.value.trim();
                    if (keyword) traceOrigin(keyword);
                }
            });
        }
    });
} else {
    mainInit();
    
    // QA Event listeners
    const qaSubmit = document.getElementById('qa-submit');
    if (qaSubmit) {
        qaSubmit.addEventListener('click', submitQuestion);
    }

    const qaQuestion = document.getElementById('qa-question');
    if (qaQuestion) {
        qaQuestion.addEventListener('keydown', function(e) {
            // Enter alone submits, Shift+Enter adds new line
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitQuestion();
            }
        });
    }
}
// Helper — global tab switcher
function switchTab(tabId) {
    document.querySelectorAll('.nav-item').forEach(n => {
        if (n.dataset.tab === tabId) {
            n.click();
        }
    });
}

async function traceOrigin(keyword) {
    // Switch to origin tracer tab
    switchTab('origin-tracer');

    // Pre-fill input
    const input = document.getElementById('origin-keyword');
    if (input) input.value = keyword;

    const resultsDiv = document.getElementById('origin-results');
    if (!resultsDiv) return;

    // Show loader
    resultsDiv.innerHTML = `
        <div class="empty-state">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            <p>Tracing narrative origin…</p>
        </div>`;

    try {
        const platform = document.getElementById('origin-platform')?.value || '';
        const url = `${API}/api/narratives/origin?keyword=${encodeURIComponent(keyword)}${platform ? '&platform=' + platform : ''}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.error || !data.origin) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <p>${data.message || 'Not enough collected data to trace this narrative reliably.'}</p>
                </div>`;
            return;
        }

        renderOriginResult(data);

    } catch (err) {
        console.error('Origin trace error:', err);
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <p>Trace could not be completed. Please try again.</p>
            </div>`;
    }
}

function renderOriginResult(data) {
    const resultsDiv = document.getElementById('origin-results');

    // Spread timeline chips
    const timelineHtml = (data.spread_timeline || []).map(t => {
        const cls = t.platform === '4chan' ? 'fourchan' : t.platform === 'mastodon' ? 'mastodon' : 'truthsocial';
        const label = t.platform === 'truthsocial' ? 'Truth Social' : t.platform;
        return `
            <div class="spread-platform-chip">
                <span class="spread-day">Day ${t.first_seen_day}</span>
                <span class="spread-platform-name">
                    <span class="platform-badge ${cls}">${label}</span>
                </span>
                <span class="spread-post-count">${t.total_posts} posts</span>
            </div>`;
    }).join('');

    // Amplifiers
    const ampHtml = (data.top_amplifiers || []).map((a, i) => {
        const cls = a.platform === '4chan' ? 'fourchan' : a.platform === 'mastodon' ? 'mastodon' : 'truthsocial';
        const label = a.platform === 'truthsocial' ? 'Truth Social' : a.platform;
        const followers = a.followers ? `${(a.followers / 1000).toFixed(0)}K followers` : '';
        const date = a.posted_at ? new Date(a.posted_at).toLocaleDateString() : '';
        return `
            <div class="amplifier-row">
                <div>
                    <span class="amplifier-name">${i + 1}. @${escapeHtml(a.author)}</span>
                    <span class="amplifier-meta" style="margin-left:0.75rem;">
                        <span class="platform-badge ${cls}">${label}</span>
                        Day ${a.day_number} · ${date}
                        ${followers ? '· ' + followers : ''}
                    </span>
                    <div style="margin-top:0.4rem; font-size:var(--fs-sm); color:var(--text-secondary); font-style:italic;">
                        "${escapeHtml(a.content_snippet)}"
                    </div>
                </div>
            </div>`;
    }).join('');

    // Coordination badge
    const isCoordinated = data.coordination_signal === 'POSSIBLE COORDINATED AMPLIFICATION';
    const coordBadge = `
        <span class="coordination-badge ${isCoordinated ? 'coordinated' : 'organic'}">
            ${isCoordinated ? '⚠ Possible Coordinated Amplification' : '✓ Organic Spread'}
        </span>`;

    const coordNote = isCoordinated && data.coordination_window_minutes
        ? `<p style="margin-top:0.75rem; font-size:var(--fs-sm); color:var(--text-secondary);">
            Top amplifiers posted within a <strong>${data.coordination_window_minutes}-minute window</strong>.
            This is a timing observation only — it does not constitute proof of coordination.
           </p>`
        : '';

    // Origin post
    if (!data.origin) return;
    const originCls = data.origin.platform === '4chan' ? 'fourchan' : data.origin.platform === 'mastodon' ? 'mastodon' : 'truthsocial';
    const originLabel = data.origin.platform === 'truthsocial' ? 'Truth Social' : data.origin.platform;
    const originDate = data.origin.posted_at ? new Date(data.origin.posted_at).toLocaleString() : '';

    resultsDiv.innerHTML = `
        <div class="origin-result">

            <!-- Summary row -->
            <div class="origin-section">
                <div class="origin-summary-row">
                    <div class="origin-metric">
                        <span class="origin-metric-value">${data.spread_timeline?.length || 1}</span>
                        <span class="origin-metric-label">Platforms</span>
                    </div>
                    <div class="origin-metric">
                        <span class="origin-metric-value">${data.total_posts_found}</span>
                        <span class="origin-metric-label">Total Posts</span>
                    </div>
                </div>
            </div>

            <!-- Origin post -->
            <div class="origin-section">
                <span class="origin-section-label">Origin — First Post Detected</span>
                <div class="origin-post">
                    <div class="origin-post-meta">
                        <span class="platform-badge ${originCls}">${originLabel}</span>
                        <span class="post-author">@${escapeHtml(data.origin.author)}</span>
                        <span class="post-time">${originDate}</span>
                        ${data.origin.board_or_feed ? `<span class="post-board">${escapeHtml(data.origin.board_or_feed)}</span>` : ''}
                    </div>
                    <div class="origin-post-content">"${escapeHtml(data.origin.content_snippet)}"</div>
                </div>
            </div>

            <!-- Spread timeline -->
            <div class="origin-section">
                <span class="origin-section-label">Spread Timeline — Platform by Platform</span>
                <div class="spread-timeline">${timelineHtml}</div>
            </div>

            <!-- Top amplifiers -->
            <div class="origin-section">
                <span class="origin-section-label">Early Amplifiers — First Accounts to Spread It</span>
                ${ampHtml || '<p style="color:var(--text-secondary);">No named amplifiers found.</p>'}
            </div>

            <!-- Coordination signal -->
            <div class="origin-section">
                <span class="origin-section-label">Amplification Pattern</span>
                ${coordBadge}
                ${coordNote}
            </div>

            <!-- Actions -->
            <div class="origin-section">
                <div class="origin-actions">
                    <button class="btn-primary" onclick="switchToExplorerWithKeyword('${escapeHtml(data.keyword)}')">
                        Search Posts
                    </button>
                    <button class="btn-accent" onclick="prefillQAQuestion('Are people spreading ${escapeHtml(data.keyword)} narratives?')">
                        Ask the Data
                    </button>
                </div>
                <p style="margin-top:1rem; font-size:var(--fs-xs); color:var(--text-secondary); font-style:italic;">
                    ⚠ ${data.limitation_note}
                </p>
            </div>

        </div>`;
}

// Helper — switch to Post Explorer with keyword pre-filled
function switchToExplorerWithKeyword(keyword) {
    switchTab('explorer');
    const input = document.getElementById('search-keyword');
    if (input) {
        input.value = keyword;
        document.getElementById('search-btn').click();
    }
}

// Helper — switch to Ask the Data with question pre-filled
function prefillQAQuestion(question) {
    switchTab('qa');
    const input = document.getElementById('qa-question');
    if (input) input.value = question;
}

// Global listeners for Origin Tracer
document.addEventListener('click', function(e) {
    const traceBtn = e.target.closest('.btn-trace-origin');
    if (traceBtn) {
        const keyword = traceBtn.getAttribute('data-keyword');
        if (keyword) traceOrigin(keyword);
    }
});
