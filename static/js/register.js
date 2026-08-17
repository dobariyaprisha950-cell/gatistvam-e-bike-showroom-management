/* =====================================================
   Gatistvam E-Bike — Register Branch Page Scripts
===================================================== */

document.addEventListener('DOMContentLoaded', function () {

  var registerForm       = document.getElementById('registerForm');

  // Branch Selection Elements
  var branchSelect       = document.getElementById('branchSelect');
  var branchNameInput    = document.getElementById('branchNameInput');
  var toggleAddBranchBtn = document.getElementById('toggleAddBranchBtn');
  var isNewBranch        = false;

  // Other Input Elements
  var ownerNameInput      = document.getElementById('ownerName');
  var mobileInput          = document.getElementById('mobileNumber');
  var usernameInput        = document.getElementById('username');
  var passwordInput        = document.getElementById('password');
  var confirmPasswordInput = document.getElementById('confirmPassword');
  var branchAddressInput   = document.getElementById('branchAddress');

  // Password Toggle Elements
  var togglePasswordBtn        = document.getElementById('togglePassword');
  var toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');
  var eyeIconPassword           = document.getElementById('eyeIconPassword');
  var eyeIconConfirm            = document.getElementById('eyeIconConfirm');

  /* ---------- Branch Dropdown / + Add Toggle Logic ---------- */
  if (toggleAddBranchBtn) {
      toggleAddBranchBtn.addEventListener('click', function() {
          isNewBranch = !isNewBranch;
          if (isNewBranch) {
              if (branchSelect) branchSelect.style.display = 'none';
              if (branchNameInput) {
                  branchNameInput.style.display = 'block';
                  branchNameInput.value = '';
                  branchNameInput.focus();
              }
              toggleAddBranchBtn.textContent = '✕';
              toggleAddBranchBtn.style.background = '#ef4444';
              toggleAddBranchBtn.title = "Select Existing Branch";
          } else {
              if (branchSelect) branchSelect.style.display = 'block';
              if (branchNameInput) branchNameInput.style.display = 'none';
              toggleAddBranchBtn.textContent = '+';
              toggleAddBranchBtn.style.background = '#2563eb';
              toggleAddBranchBtn.title = "Add New Branch";
          }
      });
  }

  /* ---------- Reusable Password Toggle ---------- */
  function wireToggle(btn, input, icon) {
      if (!btn || !input || !icon) return;

      btn.addEventListener("click", function () {
          const isHidden = input.type === "password";
          input.type = isHidden ? "text" : "password";

          if (icon.tagName.toLowerCase() === 'img') {
              icon.src = isHidden
                  ? "/static/icon/eye-off.svg"
                  : "/static/icon/eye.svg";
              icon.alt = isHidden ? "Hide Password" : "Show Password";
          }
      });
  }

  wireToggle(togglePasswordBtn, passwordInput, eyeIconPassword);
  wireToggle(toggleConfirmPasswordBtn, confirmPasswordInput, eyeIconConfirm);

  /* ---------- Live Validation Events ---------- */
  if (branchNameInput) branchNameInput.addEventListener("blur", () => { if (isNewBranch) validateRequired(branchNameInput); });
  if (ownerNameInput) ownerNameInput.addEventListener("blur", () => validateRequired(ownerNameInput));
  if (usernameInput) usernameInput.addEventListener("blur", () => validateRequired(usernameInput));
  if (branchAddressInput) branchAddressInput.addEventListener("blur", () => validateRequired(branchAddressInput));
  if (mobileInput) mobileInput.addEventListener("blur", validateMobile);
  if (passwordInput) passwordInput.addEventListener("blur", validatePassword);
  if (confirmPasswordInput) confirmPasswordInput.addEventListener("blur", validateConfirmPassword);

  /* ---------- Form Submission Handler ---------- */
  if (registerForm) {
      registerForm.addEventListener("submit", function (e) {
          e.preventDefault();

          // Validate Branch Selection / Input
          if (isNewBranch) {
              if (!validateRequired(branchNameInput)) return;
          } else {
              if (!branchSelect || !branchSelect.value) {
                  showToast(branchSelect || registerForm, "Please select a branch or click + to add new");
                  return;
              }
          }

          // Validate Rest of Fields
          if (
              !validateRequired(ownerNameInput) ||
              !validateMobile() ||
              !validateRequired(usernameInput) ||
              !validatePassword() ||
              !validateConfirmPassword() ||
              !validateRequired(branchAddressInput)
          ) {
              return;
          }

          submitRegistration();
      });
  }

  /* ---------- Validation Helpers ---------- */
  function validateRequired(input) {
      if (!input || input.value.trim() === "") {
          if (input) showToast(input, (input.placeholder || "This field") + " is required");
          return false;
      }
      return true;
  }

  function validateMobile() {
      if (!validateRequired(mobileInput)) return false;

      const mobile = mobileInput.value.trim();
      if (!/^[6-9][0-9]{9}$/.test(mobile)) {
          showToast(mobileInput, "Enter a valid 10-digit mobile number");
          mobileInput.focus();
          return false;
      }
      return true;
  }

  function validatePassword() {
      if (!validateRequired(passwordInput)) return false;

      if (passwordInput.value.length < 8) {
          showToast(passwordInput, "Password must be at least 8 characters");
          return false;
      }
      return true;
  }

  function validateConfirmPassword() {
      if (!validateRequired(confirmPasswordInput)) return false;

      if (passwordInput.value !== confirmPasswordInput.value) {
          showToast(confirmPasswordInput, "Passwords do not match");
          return false;
      }
      return true;
  }

  /* ---------- Submit Registration AJAX ---------- */
  function submitRegistration() {
      var registerBtn = registerForm.querySelector('.btn-register') || registerForm.querySelector('button[type="submit"]');
      var originalText = registerBtn ? registerBtn.textContent : 'Register';

      var csrfTokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
      var csrfToken = csrfTokenInput ? csrfTokenInput.value : getCookie('csrftoken');

      var selectedBranchId = isNewBranch ? '' : (branchSelect ? branchSelect.value : '');
      var typedBranchName  = isNewBranch ? branchNameInput.value.trim() : '';

      if (registerBtn) {
          registerBtn.disabled = true;
          registerBtn.textContent = 'Registering...';
      }

      fetch(window.location.href, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({
              branch_id: selectedBranchId,
              branch_name: typedBranchName,
              owner_name: ownerNameInput.value.trim(),
              mobile_number: mobileInput.value.trim(),
              username: usernameInput.value.trim(),
              password: passwordInput.value,
              confirm_password: confirmPasswordInput.value,
              branch_address: branchAddressInput.value.trim()
          })
      })
      .then(function (res) {
          return res.json().then(data => ({ status: res.status, body: data }));
      })
      .then(function (result) {
          var data = result.body;
          if (data.success) {
              if (registerBtn) showToast(registerBtn, "Registration Successful!", "success");
              setTimeout(function () {
                  window.location.href = data.redirect_url || '/yakuza/login/';
              }, 1000);
          } else {
              if (registerBtn) {
                  registerBtn.disabled = false;
                  registerBtn.textContent = originalText;
                  showToast(registerBtn, data.message || "Registration failed", "error");
              }
          }
      })
      .catch(function (err) {
          if (registerBtn) {
              registerBtn.disabled = false;
              registerBtn.textContent = originalText;
              showToast(registerBtn, err.message || "Something went wrong. Please try again.", "error");
          }
      });
  }

  /* ---------- CSRF Helper ---------- */
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

  /* ---------- Toast Message Helper ---------- */
  function showToast(input, message, type = "error") {
      const toast = document.getElementById("inlineToast");
      if (!toast) return;

      if (type === "success") {
          toast.style.position = "fixed";
          toast.style.left = "50%";
          toast.style.top = "50%";
          toast.style.transform = "translate(-50%, -50%)";
          toast.innerHTML = '<span style="color:#22c55e;">✔</span> ' + message;
      } else {
          toast.style.position = "fixed";
          let group = input.closest(".input-group") || input;
          let rect = group.getBoundingClientRect();

          toast.innerHTML = '<span style="color:#F4B400;">⚠</span> ' + message;
          toast.style.left = rect.left + "px";
          toast.style.top = (rect.bottom + 6) + "px";
          toast.style.transform = "none";
      }

      toast.classList.add("show");

      clearTimeout(toast.timer);
      toast.timer = setTimeout(function () {
          toast.classList.remove("show");
      }, 3000);
  }
});