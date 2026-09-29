document.querySelectorAll('.math').forEach(element => {
  try {
    katex.render(element.textContent, element, {
      displayMode: element.classList.contains('math-block'),
      throwOnError: true,
      trust: false,
      strict: 'warn',
      output: 'htmlAndMathml'
    });
  } catch (error) {
    element.classList.add('math-error');
    console.error('公式渲染失败', error);
  }
});

const headings = Array.from(document.querySelectorAll('.prose h2, .prose h3'));
const links = Array.from(document.querySelectorAll('.toc-links a'));
let pending = false;
function updateDirectory() {
  const current = headings.filter(heading => heading.getBoundingClientRect().top <= 140).pop() || headings[0];
  links.forEach(link => {
    const active = current && link.hash === '#' + current.id;
    link.classList.toggle('active', Boolean(active));
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  pending = false;
}
window.addEventListener('scroll', () => {
  if (!pending) {
    pending = true;
    requestAnimationFrame(updateDirectory);
  }
}, {passive: true});
updateDirectory();
