function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.card, .metric-card, .dashboard-card').forEach((card, index) => {
    card.style.animationDelay = `${Math.min(index * 18, 180)}ms`;
    card.classList.add('ui-enter');
  });

  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      const submitter = form.querySelector('button[type="submit"], button:not([type]), .btn-primary');
      if (!submitter || submitter.dataset.keepLabel === 'true') return;
      submitter.dataset.originalText = submitter.innerHTML;
      submitter.classList.add('disabled');
    });
  });
});
