/* =========================================================
   Github Ranking — Main JS
   Language toggle · Sidebar · Back-to-top · Relative dates
   ========================================================= */

const LANG_KEY = 'gh-ranking-lang';

/* ── Language ─────────────────────────────────────────── */
function getLang() {
  return localStorage.getItem(LANG_KEY) || 'en';
}

function applyLang(lang) {
  document.documentElement.setAttribute('data-lang', lang);
  localStorage.setItem(LANG_KEY, lang);
  const btn = document.getElementById('lang-btn');
  if (btn) btn.textContent = lang === 'zh' ? 'EN' : '中文';
}

function toggleLang() {
  applyLang(getLang() === 'zh' ? 'en' : 'zh');
}

/* ── Sidebar (mobile) ──────────────────────────────────── */
function toggleSidebar() {
  const sidebar  = document.getElementById('sidebar');
  const overlay  = document.getElementById('sidebar-overlay');
  const isOpen   = sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('active', isOpen);
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('active');
}

/* ── Back-to-top ───────────────────────────────────────── */
function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  const update = () => btn.classList.toggle('visible', window.scrollY > 400);
  window.addEventListener('scroll', update, { passive: true });
  update();
}

/* ── Active nav link (Intersection Observer) ───────────── */
function initActiveNav() {
  const sections  = document.querySelectorAll('.ranking-section[id]');
  const navLinks  = document.querySelectorAll('.nav-link[data-section]');
  if (!sections.length || !navLinks.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      navLinks.forEach(link => {
        link.classList.toggle('active', link.dataset.section === entry.target.id);
      });
    });
  }, { rootMargin: '-56px 0px -60% 0px', threshold: 0 });

  sections.forEach(s => observer.observe(s));
}

/* ── Relative date formatting ──────────────────────────── */
function formatRelDate(isoStr) {
  if (!isoStr) return '';
  const diff = (Date.now() - new Date(isoStr)) / 1000;
  if (diff < 60)           return 'just now';
  if (diff < 3600)         return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)        return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 30)   return `${Math.floor(diff / 86400)}d ago`;
  if (diff < 86400 * 365)  return `${Math.floor(diff / (86400 * 30))}mo ago`;
  return `${Math.floor(diff / (86400 * 365))}y ago`;
}

function applyRelDates() {
  document.querySelectorAll('[data-date]').forEach(el => {
    const raw = el.dataset.date;
    if (!raw) return;
    const rel = formatRelDate(raw);
    const abs = raw.slice(0, 10);
    el.textContent = rel;
    el.title = abs;
  });
}

/* ── Init ──────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  applyLang(getLang());
  initBackToTop();
  initActiveNav();
  applyRelDates();

  // Close sidebar when overlay is clicked
  const overlay = document.getElementById('sidebar-overlay');
  if (overlay) overlay.addEventListener('click', closeSidebar);

  // Close sidebar on nav link click (mobile)
  document.querySelectorAll('.sidebar .nav-link').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) closeSidebar();
    });
  });
});
