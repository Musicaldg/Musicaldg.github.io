document.querySelectorAll('.series-folder').forEach(folder => {
  const summary = folder.querySelector('summary');
  if (!summary) return;
  summary.addEventListener('click', () => {
    window.requestAnimationFrame(() => {
      if (folder.open) {
        folder.classList.add('is-open');
      } else {
        folder.classList.remove('is-open');
      }
    });
  });
  if (folder.open) folder.classList.add('is-open');
});
