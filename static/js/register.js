/* =====================================================
   Gatistvam E-Bike — Register Branch Page Scripts
===================================================== */

document.addEventListener('DOMContentLoaded', function () {

  var registerForm       = document.getElementById('registerForm');

  var branchNameInput    = document.getElementById('branchName');
  var ownerNameInput      = document.getElementById('ownerName');
  var mobileInput          = document.getElementById('mobileNumber');
  var emailInput            = document.getElementById('emailAddress');
  var usernameInput        = document.getElementById('username');
  var passwordInput        = document.getElementById('password');
  var confirmPasswordInput = document.getElementById('confirmPassword');
  var branchAddressInput   = document.getElementById('branchAddress');

  var togglePasswordBtn        = document.getElementById('togglePassword');
  var toggleConfirmPasswordBtn = document.getElementById('toggleConfirmPassword');
  var eyeIconPassword           = document.getElementById('eyeIconPassword');
  var eyeIconConfirm            = document.getElementById('eyeIconConfirm');

  var EYE_OPEN =
    '<path d="M12 5C5.63636 5 1 12 1 12C1 12 5.63636 19 12 19C18.3636 19 23 12 23 12C23 12 18.3636 5 12 5Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8"/>';

  var EYE_CLOSED =
    '<path d="M3 3L21 21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>' +
    '<path d="M10.6 10.7C10.2 11.1 10 11.5 10 12C10 13.1 10.9 14 12 14C12.5 14 12.9 13.8 13.3 13.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<path d="M6.5 6.7C4.1 8.2 2 11 2 11C2 11 5.64 17.8 12 17.8C13.6 17.8 15 17.4 16.2 16.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>' +
    '<path d="M9.5 5.4C10.3 5.1 11.1 5 12 5C18.36 5 22 11.8 22 11.8C22 11.8 21.2 13.4 19.6 15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>';

  /* ---------- Reusable password toggle ---------- */
  function wireToggle(btn, input, icon) {

    if (!btn || !input || !icon) return;

    btn.addEventListener("click", function () {

        const hidden = input.type === "password";

        input.type = hidden ? "text" : "password";

        icon.src = hidden
            ? "/static/icon/eye-off.svg"
            : "/static/icon/eye.svg";

        icon.alt = hidden
            ? "Hide Password"
            : "Show Password";
    });

}
  wireToggle(togglePasswordBtn, passwordInput, eyeIconPassword);
  wireToggle(toggleConfirmPasswordBtn, confirmPasswordInput, eyeIconConfirm);
/* ---------- Live Validation ---------- */

branchNameInput.addEventListener("blur",()=>validateRequired(branchNameInput));
ownerNameInput.addEventListener("blur",()=>validateRequired(ownerNameInput));
usernameInput.addEventListener("blur",()=>validateRequired(usernameInput));
branchAddressInput.addEventListener("blur",()=>validateRequired(branchAddressInput));

mobileInput.addEventListener("blur",validateMobile);

emailInput.addEventListener("blur",validateEmail);

passwordInput.addEventListener("blur",validatePassword);

confirmPasswordInput.addEventListener("blur",validateConfirmPassword);
  /* ---------- Validation + submit ---------- */
  registerForm.addEventListener("submit",function(e){

    e.preventDefault();

    if(
        !validateRequired(branchNameInput) ||
        !validateRequired(ownerNameInput) ||
        !validateMobile() ||
        !validateEmail() ||
        !validateRequired(usernameInput) ||
        !validatePassword() ||
        !validateConfirmPassword() ||
        !validateRequired(branchAddressInput)
    ){
        return;
    }

    submitRegistration();

});

 
function validateRequired(input){

    if(input.value.trim()===""){
        showToast(input,input.placeholder+" is required");
        return false;
    }

    return true;
}

function validateEmail(){

    if(!validateRequired(emailInput)) return false;

    const email = emailInput.value.trim();

    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){
        showToast(emailInput,"Please enter valid email");
        emailInput.focus();
        return false;
    }

    return true;
}
function isValidEmail(email){
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isValidMobile(value){
    return /^[6-9][0-9]{9}$/.test(value);
}

function validateMobile(){

    if(!validateRequired(mobileInput)) return false;

    const mobile = mobileInput.value.trim();

    if(!/^[6-9][0-9]{9}$/.test(mobile)){
        showToast(mobileInput,"Enter valid mobile number");
        mobileInput.focus();
        return false;
    }

    return true;
}

function validatePassword(){

    if(!validateRequired(passwordInput)) return false;

    if(passwordInput.value.length<8){
        showToast(passwordInput,"Password must be at least 8 characters");
        return false;
    }

    return true;
}

function validateConfirmPassword(){

    if(!validateRequired(confirmPasswordInput)) return false;

    if(passwordInput.value!==confirmPasswordInput.value){
        showToast(confirmPasswordInput,"Passwords do not match");
        return false;
    }

    return true;
}
   function submitRegistration() {
    var registerBtn = registerForm.querySelector('.btn-register');
    var originalText = registerBtn.textContent;

    registerBtn.disabled = true;
    registerBtn.textContent = 'Registering...';
    
    /*
      Django integration point:
      Replace this block with a fetch() call to your registration endpoint, e.g.

      fetch('/yakuza/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
          branch_name: branchNameInput.value.trim(),
          owner_name: ownerNameInput.value.trim(),
          mobile_number: mobileInput.value.trim(),
          email: emailInput.value.trim(),
          username: usernameInput.value.trim(),
          password: passwordInput.value,
          confirm_password: confirmPasswordInput.value,
          branch_address: branchAddressInput.value.trim()
        })
      })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.success) {
          window.location.href = data.redirect_url || '/login/';
        } else {
          registerBtn.disabled = false;
          registerBtn.textContent = originalText;
          alert(data.message || 'Registration failed. Please check your details.');
        }
      })
      .catch(function () {
        registerBtn.disabled = false;
        registerBtn.textContent = originalText;
        alert('Something went wrong. Please try again.');
      });
    */

    window.setTimeout(function () {

    registerBtn.disabled = false;
    registerBtn.textContent = originalText;

    showToast(registerBtn,"Registration Successful","success");

},800);
  }

  /* ---------- CSRF helper for Django ---------- */
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
function showToast(input,message,type="error"){

    const toast=document.getElementById("inlineToast");

if(type==="success"){

    toast.style.position="fixed";

    toast.innerHTML='<span style="color:#22c55e;">✔</span> '+message;

    toast.style.left="50%";
    toast.style.top="50%";
    toast.style.transform="translate(-50%,-50%)";

}
else{

    toast.style.position="absolute";

    let group=input.closest(".input-group");

    let rect=group.getBoundingClientRect();

    toast.innerHTML='<span style="color:#F4B400;">⚠</span> '+message;

    toast.style.left=rect.left+"px";
    toast.style.top=(window.scrollY+rect.bottom-8)+"px";
}
    toast.classList.add("show");

    clearTimeout(toast.timer);

    toast.timer=setTimeout(function(){
        toast.classList.remove("show");
    },3000);

}

});
