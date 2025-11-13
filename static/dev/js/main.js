/* ============================================
   BThinkX Dashboard Main JavaScript
   ============================================ */

// Theme Toggle
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        });

        // Load saved theme
        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    // Sidebar Toggle
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');

    if (sidebarToggle && sidebar && mainContent) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });

        // Close sidebar on mobile when clicking outside
        document.addEventListener('click', function(event) {
            if (!event.target.closest('.sidebar') && !event.target.closest('.sidebar-toggle')) {
                sidebar.classList.remove('show');
            }
        });

        // Handle responsive behavior
        function handleResize() {
            if (window.innerWidth > 768) {
                sidebar.classList.remove('show');
                mainContent.classList.remove('expanded');
            }
        }

        window.addEventListener('resize', handleResize);
        handleResize(); // Run on page load
    }

    // Dropdown Menu
    const userButton = document.querySelector('.user-button');
    const dropdownMenu = document.querySelector('.dropdown-menu');

    if (userButton && dropdownMenu) {
        userButton.addEventListener('click', function(e) {
            e.preventDefault();
            dropdownMenu.classList.toggle('show');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(event) {
            if (!event.target.closest('.user-button') && !event.target.closest('.dropdown-menu')) {
                dropdownMenu.classList.remove('show');
            }
        });
    }

    // Close dropdown when selecting an item
    const dropdownItems = document.querySelectorAll('.dropdown-item');
    dropdownItems.forEach(item => {
        item.addEventListener('click', function() {
            if (dropdownMenu) {
                dropdownMenu.classList.remove('show');
            }
        });
    });

    // Notification Dropdown
    const notificationButton = document.querySelector('[data-dropdown="notifications"]');
    const notificationMenu = document.querySelector('.dropdown-menu[data-dropdown="notifications"]');

    if (notificationButton && notificationMenu) {
        notificationButton.addEventListener('click', function(e) {
            e.preventDefault();
            notificationMenu.classList.toggle('show');
        });

        // Close when clicking outside
        document.addEventListener('click', function(event) {
            if (!event.target.closest('[data-dropdown="notifications"]')) {
                notificationMenu.classList.remove('show');
            }
        });
    }
});

// Navigation Active State
function setActiveNav() {
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-menu-item');

    navItems.forEach(item => {
        const link = item.querySelector('a');
        if (link && link.href.includes(currentPath)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// Call on page load
document.addEventListener('DOMContentLoaded', setActiveNav);

// Utility function for dismissing alerts
function dismissAlert(element) {
    element.style.animation = 'slideUp 0.3s ease';
    setTimeout(() => {
        element.remove();
    }, 300);
}

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert-banner');
    alerts.forEach(alert => {
        setTimeout(() => {
            dismissAlert(alert);
        }, 5000);
    });
});
