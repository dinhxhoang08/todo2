(function() {
    const toggle = document.getElementById('theme-toggle');
    const html = document.documentElement;

    function getPreferred() {
        const stored = localStorage.getItem('theme');
        if (stored) return stored;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function apply(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        if (toggle) {
            toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
            toggle.title = theme === 'dark' ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối';
        }
    }

    apply(getPreferred());

    if (toggle) {
        toggle.addEventListener('click', function() {
            var current = html.getAttribute('data-theme') || 'light';
            apply(current === 'dark' ? 'light' : 'dark');
        });
    }
})();
