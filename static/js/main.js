// Core UI Interactions
document.addEventListener('DOMContentLoaded', () => {
  // Mobile Sidebar Toggle
  const sidebarToggle = document.getElementById('mobileSidebarToggle');
  const sidebar = document.getElementById('dashboardSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  if (sidebarToggle && sidebar && backdrop) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      backdrop.classList.toggle('active');
    });

    backdrop.addEventListener('click', () => {
      sidebar.classList.remove('open');
      backdrop.classList.remove('active');
    });
  }

  // Auto-dismiss alert banners after 5 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-10px)';
      setTimeout(() => alert.remove(), 300);
    }, 5000);
  });

  // Collapsible category tree toggles
  const categoryHeaders = document.querySelectorAll('.category-parent-header');
  categoryHeaders.forEach(header => {
    header.addEventListener('click', () => {
      const sublist = header.nextElementSibling;
      if (sublist && sublist.classList.contains('subcategory-list')) {
        const isHidden = sublist.style.display === 'none';
        sublist.style.display = isHidden ? 'block' : 'none';
        const chevron = header.querySelector('.tree-chevron');
        if (chevron) {
          chevron.style.transform = isHidden ? 'rotate(90deg)' : 'rotate(0deg)';
        }
      }
    });
  });
});
