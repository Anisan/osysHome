document.querySelector('.theme-toggle').addEventListener('click', () => {
  const bodyTag = document.querySelector('[data-tag="body"]');
  const currentTheme = bodyTag.getAttribute('data-bs-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  console.log(newTheme)
  switch (newTheme) {
    case "dark":
      bodyTag.setAttribute('data-bs-theme', "dark");
      window.localStorage.setItem('dark-theme', true);
      break;
    default:
      bodyTag.setAttribute('data-bs-theme', "light");
      window.localStorage.setItem('dark-theme', false);
  }
});