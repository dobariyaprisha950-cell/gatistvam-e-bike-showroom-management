/* =====================================================
   Gatistvam E-Bike — Login Page Scripts
===================================================== */

document.addEventListener('DOMContentLoaded', function () {

  var passwordInput   = document.getElementById('password');
  var toggleBtn        = document.getElementById('togglePassword');
  var eyeIcon           = document.getElementById('eyeIcon');
  var loginForm         = document.getElementById('loginForm');
  var usernameInput    = document.getElementById('username');
  var securityBtn       = document.getElementById('securityLoginBtn');

  var EYE_OPEN =
    '<path d="M12 5C5.63636 5 1 12 1 12C1 12 5.63636 19 12 19C18.3636 19 23 12 23 12C23 12 18.3636 5 12 5Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8"/>';

  var EYE_CLOSED =
    '<path d="M3 3L21 21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' +
    '<path d="M10.6 10.7C10.2 11.1 10 11.5 10 12C10 13.1 10.9 14 12 14C12.5 14 12.9 13.8 13.3 13.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<path d="M6.5 6.7C4.1 8.2 2 11 2 11C2 11 5.64 17.8 12 17.8C13.6 17.8 15 17.4 16.2 16.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<path d="M9.5 5.4C10.3 5.1 11.1 5 12 5C18.36 5 22 11.8 22 11.8C22 11.8 21.2 13.4 19.6 15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>';

  /* ---------- Toggle password visibility ---------- */
  if (toggleBtn && passwordInput && eyeIcon) {
    toggleBtn.addEventListener('click', function () {
      var isHidden = passwordInput.getAttribute('type') === 'password';

      passwordInput.setAttribute('type', isHidden ? 'text' : 'password');
      eyeIcon.innerHTML = isHidden ? EYE_CLOSED : EYE_OPEN;
      toggleBtn.classList.toggle('active', isHidden);
      toggleBtn.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
    });
  }

  /* ---------- Client-side validation + submit ---------- */
  /* ---------- Form Submit Handler ---------- */
if (loginForm) {
  loginForm.addEventListener('submit', function (e) {
    var username = usernameInput.value.trim();
    var password = passwordInput.value.trim();

    if (!username) {
      e.preventDefault();
      showToast(usernameInput, "Username is required", "warning");
      usernameInput.focus();
      return;
    }

    if (!password) {
      e.preventDefault();
      showToast(passwordInput, "Password is required", "warning");
      passwordInput.focus();
      return;
    }

    // હવે e.preventDefault() નહિ થાય, Standard POST Request જશે અને Django ડાયરેક્ટ રીડાયરેક્ટ કરી દેશે.
  });
}
    


  function markFieldError(inputEl) {
    var group = inputEl.closest('.input-group');
    if (group) {
      inputEl.focus();
    }
  }

  function clearFieldErrors() {
    var groups = document.querySelectorAll('.input-group');
    groups.forEach(function (group) {
      group.style.borderColor = '';
      group.style.boxShadow = '';
    });
  }

  /* ---------- Backend Connected Submit Function ---------- */
  function submitLogin(username, password) {
    var loginBtn = loginForm.querySelector('.btn-login');
    var originalText = loginBtn.textContent;

    loginBtn.disabled = true;
    loginBtn.textContent = 'Logging in...';

    var formData = new FormData(loginForm);

    fetch(loginForm.action || window.location.href, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: formData
    })
    .then(function (res) {
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }
      return res.json();
    })
    .then(function (data) {
      if (!data) return;

      if (data.success) {
        showToast(loginBtn, "Login Successful!", "success");
        setTimeout(function() {
          window.location.href = data.redirect_url || '/dashboard/';
        }, 600);
      } else {
        loginBtn.disabled = false;
        loginBtn.textContent = originalText;
        showToast(loginBtn, data.message || 'Invalid username or password.', 'warning');
      }
    })
    .catch(function (err) {
      // Direct form submit fallback if AJAX faces response issues
      loginForm.submit();
    });
  }

  /* ---------- Security option click ---------- */
  if (securityBtn) {
    securityBtn.addEventListener('click', function () {
      console.log('Login with Security Option clicked');
    });
  }

  /* ---------- CSRF Helper for Django ---------- */
  function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      var cookies = document.cookie.split(';');
      for (var i = 0; i < cookies.length; i++) {
        var cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /* ---------- Inline Toast Display ---------- */
  function showToast(input, message, type = "warning") {
    const toast = document.getElementById("inlineToast");
    if (!toast) return;

    if (type === "success") {
      toast.style.left = "50%";
      toast.style.top = "50%";
      toast.style.transform = "translate(-50%, -50%)";
      toast.innerHTML = '<span style="color:#22C55E;">✔</span> ' + message;
    } else {
      const group = input.closest(".input-group") || input;
      const rect = group.getBoundingClientRect();

      toast.style.transform = "none";
      toast.style.left = rect.left + "px";
      toast.style.top = (window.scrollY + rect.bottom + 5) + "px";
      toast.innerHTML = '<span style="color:#F4B400;">⚠</span> ' + message;
    }

    toast.classList.add("show");

    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => {
      toast.classList.remove("show");
    }, 3000);
  }

});