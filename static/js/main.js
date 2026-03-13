/* ===== Sidebar Toggle ===== */
const sidebar = document.getElementById('sidebar');
const mainWrapper = document.getElementById('mainWrapper');
const sidebarToggler = document.getElementById('sidebarToggler');
const sidebarOverlay = document.getElementById('sidebarOverlay');

function isMobile() { return window.innerWidth < 992; }

if (sidebarToggler) {
    sidebarToggler.addEventListener('click', () => {
        if (isMobile()) {
            sidebar.classList.toggle('mobile-open');
            sidebarOverlay.classList.toggle('active');
        } else {
            sidebar.classList.toggle('collapsed');
            mainWrapper.classList.toggle('expanded');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        }
    });
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', () => {
        sidebar.classList.remove('mobile-open');
        sidebarOverlay.classList.remove('active');
    });
}

// Restore sidebar state on desktop
if (!isMobile() && localStorage.getItem('sidebarCollapsed') === 'true') {
    sidebar?.classList.add('collapsed');
    mainWrapper?.classList.add('expanded');
}

/* ===== Clickable table rows ===== */
document.querySelectorAll('.clickable-row').forEach(row => {
    row.style.cursor = 'pointer';
    row.addEventListener('click', () => {
        if (row.dataset.href) window.location.href = row.dataset.href;
    });
});

/* ===== Auto-dismiss alerts after 5s ===== */
document.querySelectorAll('.custom-alert').forEach(alert => {
    setTimeout(() => {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        if (bsAlert) bsAlert.close();
    }, 5000);
});

/* ===== Animate stat numbers ===== */
function animateCount(el) {
    const target = parseInt(el.textContent, 10);
    if (isNaN(target) || target === 0) return;
    let start = 0;
    const duration = 800;
    const step = Math.ceil(target / (duration / 16));
    const timer = setInterval(() => {
        start += step;
        if (start >= target) { el.textContent = target; clearInterval(timer); }
        else { el.textContent = start; }
    }, 16);
}
document.querySelectorAll('.stat-value').forEach(el => animateCount(el));

/* ===== Active nav highlight on page load ===== */
window.addEventListener('resize', () => {
    if (!isMobile()) {
        sidebar?.classList.remove('mobile-open');
        sidebarOverlay?.classList.remove('active');
    }
});
