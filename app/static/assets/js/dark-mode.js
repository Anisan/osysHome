var dragTheme = window.localStorage.getItem('dark-theme');
const darkModeSwitchInput = document.querySelector('input#darkModeSwitch');
const bodyTag = document.querySelector('[data-tag="body"]');
darkModeSwitchInput.checked = (dragTheme == "true")? true : false;
bodyTag.setAttribute('data-bs-theme', (dragTheme == "true")? "dark" : "light");

const themeSwitch = () => {
  const currentState = bodyTag.getAttribute('data-bs-theme');
  
  switch (currentState) {
    case "light":
      bodyTag.setAttribute('data-bs-theme', "dark");
      window.localStorage.setItem('dark-theme', true);
      break;
    default:
      bodyTag.setAttribute('data-bs-theme', "light");
      window.localStorage.setItem('dark-theme', false);
  }
};

darkModeSwitchInput.addEventListener('change', themeSwitch);

