document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-password-target]').forEach(function (button) {
    button.addEventListener('click', function () {
      var input = document.getElementById(button.dataset.passwordTarget);
      var icon = button.querySelector('img');
      if (!input || !icon) return;

      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      icon.src = show ? '/static/icon/eye-off.svg' : '/static/icon/eye.svg';
      button.setAttribute('aria-label', (show ? 'Hide ' : 'Show ') + (input.name === 'new_password' ? 'new password' : 'confirm password'));
    });
  });

  var form = document.querySelector('form[action$="/accounts/forgot-password/reset/"]');
  var error = document.getElementById('passwordClientError');
  if (!form || !error) return;

  form.addEventListener('submit', function (event) {
    var password = form.elements.new_password.value;
    var confirm = form.elements.confirm_password.value;
    var message = '';
    if (password.length < 6) message = 'Password must contain at least 6 characters.';
    else if (password !== confirm) message = 'The passwords do not match.';
    if (message) {
      event.preventDefault();
      error.textContent = message;
      error.hidden = false;
    }
  });
  form.addEventListener('input', function () {
    error.hidden = true;
    error.textContent = '';
  });
});
