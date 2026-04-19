/* ================================================================
   Github Ranking — Main JS
   Page transitions · Scroll reveal · Count-up · Search · Sort
   ================================================================ */

const LANG_KEY = 'gh-ranking-lang';

/* ── Language ───────────────────────────────────────── */
function getLang() { return localStorage.getItem(LANG_KEY) || 'en'; }

function applyLang(lang) {
  document.documentElement.setAttribute('data-lang', lang);
  localStorage.setItem(LANG_KEY, lang);
  const btn = document.getElementById('lang-btn');
  if (btn) btn.textContent = lang === 'zh' ? 'EN' : '中文';
}

function toggleLang() { applyLang(getLang() === 'zh' ? 'en' : 'zh'); }

/* ── Page transitions ───────────────────────────────── */
function navTo(e, url) {
  if (e) e.preventDefault();
  if (!url || url === window.location.href) return;
  document.body.classList.add('exiting');
  setTimeout(() => { window.location.href = url; }, 240);
}

function initPageTransitions() {
  document.querySelectorAll('a[href]').forEach(a => {
    const href = a.getAttribute('href') || '';
    // Skip external links, anchors, and links that already handle navigation
    if (href.startsWith('http') || href.startsWith('#') ||
        href.startsWith('mailto') || a.hasAttribute('target')) return;
    a.addEventListener('click', e => navTo(e, a.href));
  });
}

/* ── Sidebar ────────────────────────────────────────── */
function toggleSidebar() {
  const sb  = document.getElementById('sidebar');
  const ov  = document.getElementById('sidebar-overlay');
  const open = sb?.classList.toggle('open');
  ov?.classList.toggle('active', !!open);
}
function closeSidebar() {
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-overlay')?.classList.remove('active');
}

/* ── Back to top ────────────────────────────────────── */
function scrollToTop() { window.scrollTo({ top: 0, behavior: 'smooth' }); }

function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  const tick = () => btn.classList.toggle('visible', window.scrollY > 480);
  window.addEventListener('scroll', tick, { passive: true });
  tick();
}

/* ── Scroll reveal + row stagger ────────────────────── */
function staggerRows(section) {
  const rows = section.querySelectorAll('tbody tr');
  rows.forEach((row, i) => {
    row.style.animationDelay = `${i * 38 + 150}ms`;
    row.classList.add('row-in');
  });
}

function initScrollReveal() {
  const sections = document.querySelectorAll('.ranking-section');
  if (!sections.length) return;

  const obs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('revealed');
      staggerRows(entry.target);
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.04, rootMargin: '0px 0px -32px 0px' });

  sections.forEach(s => obs.observe(s));
}

/* Row stagger for standalone tables (Top100 pages) */
function initStandaloneTableStagger() {
  const card = document.querySelector('.page-hd ~ .tbl-wrap .ranking-table tbody,\
                                        .page-hd + .tbl-wrap .ranking-table tbody');
  // Use a broader selector for Top100 pages
  const table = document.querySelector('.tbl-wrap .ranking-table');
  if (!table) return;
  const rows = table.querySelectorAll('tbody tr');
  rows.forEach((row, i) => {
    row.style.animationDelay = `${i * 12}ms`;
    row.classList.add('row-in');
  });
}

/* ── Active nav link + topbar section name ──────────── */
function initActiveNav() {
  const sections = document.querySelectorAll('.ranking-section[id]');
  const navLinks = document.querySelectorAll('.sidebar .nav-link[data-section]');
  const crumbCur = document.getElementById('crumb-cur');
  if (!sections.length) return;

  const obs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const id = entry.target.id;

      navLinks.forEach(l => l.classList.toggle('active', l.dataset.section === id));

      if (crumbCur) {
        const activeLink = [...navLinks].find(l => l.dataset.section === id);
        if (activeLink) {
          const nameEl = activeLink.querySelector(
            getLang() === 'zh' ? '.text-zh' : '.text-en'
          ) || activeLink.querySelector('.text-en');
          crumbCur.style.opacity = '0';
          setTimeout(() => {
            crumbCur.textContent = nameEl?.textContent?.trim() || '';
            crumbCur.style.opacity = '1';
          }, 160);
        }
      }
    });
  }, { rootMargin: '-54px 0px -62% 0px', threshold: 0 });

  sections.forEach(s => obs.observe(s));
}

/* ── Count-up animation ─────────────────────────────── */
function countUp(el, target, duration = 1300, suffix = '') {
  if (isNaN(target)) return;
  const start = performance.now();
  const update = now => {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 3); // cubic ease-out
    el.textContent = Math.round(ease * target) + suffix;
    if (p < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

function initCountUp() {
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || '';
    if (isNaN(target)) return;
    const obs = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      countUp(el, target, 1300, suffix);
      obs.disconnect();
    });
    obs.observe(el);
  });
}

/* ── Search filter ──────────────────────────────────── */
function initSearch() {
  document.querySelectorAll('.table-search').forEach(input => {
    const tableId = input.dataset.table;
    if (!tableId) return;
    const table    = document.getElementById(tableId);
    const card     = table?.closest('.table-card');
    const noResult = card?.querySelector('.no-results');

    input.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      const rows = table?.querySelectorAll('tbody tr') || [];
      let vis = 0;
      rows.forEach(row => {
        const show = !q || row.textContent.toLowerCase().includes(q);
        row.style.display = show ? '' : 'none';
        if (show) vis++;
      });
      if (noResult) noResult.style.display = !vis ? 'block' : 'none';
    });
  });
}

/* ── Column sort ────────────────────────────────────── */
function initSort() {
  document.querySelectorAll('.ranking-table').forEach(table => {
    const ths = table.querySelectorAll('th.sortable');
    ths.forEach(th => {
      th.addEventListener('click', () => {
        const col = parseInt(th.dataset.col, 10);
        const asc = !th.classList.contains('sort-asc');
        ths.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');

        const tbody = table.querySelector('tbody');
        const rows  = [...tbody.querySelectorAll('tr')];

        rows.sort((a, b) => {
          const va = a.cells[col]?.dataset.val ?? a.cells[col]?.textContent ?? '';
          const vb = b.cells[col]?.dataset.val ?? b.cells[col]?.textContent ?? '';
          const na = parseFloat(va), nb = parseFloat(vb);
          if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
          return asc ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
        });

        rows.forEach(r => tbody.appendChild(r));
      });
    });
  });
}

/* ── Relative dates ─────────────────────────────────── */
function relDate(iso) {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60)       return 'just now';
  if (s < 3600)     return `${Math.floor(s / 60)}m ago`;
  if (s < 86400)    return `${Math.floor(s / 3600)}h ago`;
  if (s < 2592000)  return `${Math.floor(s / 86400)}d ago`;
  if (s < 31536000) return `${Math.floor(s / 2592000)}mo ago`;
  return `${Math.floor(s / 31536000)}y ago`;
}

function initRelDates() {
  document.querySelectorAll('[data-date]').forEach(el => {
    const r = relDate(el.dataset.date);
    if (r) {
      el.title = (el.dataset.date || '').slice(0, 10);
      el.textContent = r;
    }
  });
}

/* ── Nav search (jump to section) ───────────────────── */
function initNavSearch() {
  const input = document.getElementById('nav-search');
  if (!input) return;
  const links = [...document.querySelectorAll('.sidebar .nav-link')];

  input.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim();
    links.forEach(l => {
      l.style.display = !q || l.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

/* ── Init ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  applyLang(getLang());
  initPageTransitions();
  initBackToTop();
  initScrollReveal();
  initStandaloneTableStagger();
  initActiveNav();
  initCountUp();
  initSearch();
  initSort();
  initRelDates();
  initNavSearch();

  document.getElementById('sidebar-overlay')
    ?.addEventListener('click', closeSidebar);

  document.querySelectorAll('.sidebar .nav-link').forEach(l =>
    l.addEventListener('click', () => window.innerWidth <= 768 && closeSidebar())
  );
});
