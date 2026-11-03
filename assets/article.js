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
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let pending = false;
let flashTimer = 0;

function flashHeading(heading) {
  if (!heading || reduceMotion) return;
  heading.classList.remove('heading-flash');
  void heading.offsetWidth;
  heading.classList.add('heading-flash');
  window.clearTimeout(flashTimer);
  flashTimer = window.setTimeout(() => heading.classList.remove('heading-flash'), 1000);
}

function scrollToHeading(heading, updateHistory) {
  if (!heading) return;
  heading.scrollIntoView({
    behavior: reduceMotion ? 'auto' : 'smooth',
    block: 'start'
  });
  if (updateHistory) {
    history.pushState(null, '', '#' + heading.id);
  }
  flashHeading(heading);
}

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

links.forEach(link => {
  link.addEventListener('click', event => {
    const heading = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (!heading) return;
    event.preventDefault();
    scrollToHeading(heading, true);
  });
});

window.addEventListener('scroll', () => {
  if (!pending) {
    pending = true;
    requestAnimationFrame(updateDirectory);
  }
}, {passive: true});

if (location.hash) {
  const initial = document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (initial) {
    window.setTimeout(() => flashHeading(initial), 80);
  }
}

updateDirectory();
