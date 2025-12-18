document.addEventListener("DOMContentLoaded", function () {
  function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach((field) => {
      const existingError = field.parentElement.querySelector('.field-error-message');
      if (existingError) {
        existingError.remove(); 
      }
      field.classList.remove('is-invalid');
      field.classList.remove('input-error');
      if (!field.value.trim()) {
        isValid = false;
        field.classList.add('is-invalid');
        field.classList.add('input-error');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'field-error-message text-danger fs-7 mt-1';
        errorDiv.textContent = 'This field is required';
        field.parentElement.appendChild(errorDiv);
      }
      if (field.type === 'email' && field.value.trim()) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailPattern.test(field.value)) {
          isValid = false;
          field.classList.add('is-invalid');
          field.classList.add('input-error');
          
          const errorDiv = document.createElement('div');
          errorDiv.className = 'field-error-message text-danger fs-7 mt-1';
          errorDiv.textContent = 'Please enter a valid email address';
          field.parentElement.appendChild(errorDiv);
        }
      }
      if (field.type === 'tel' && field.value.trim()) {
        const phonePattern = /^[0-9+\-\s()]{10,}$/;
        if (!phonePattern.test(field.value)) {
          isValid = false;
          field.classList.add('is-invalid');
          field.classList.add('input-error');
          
          const errorDiv = document.createElement('div');
          errorDiv.className = 'field-error-message text-danger fs-7 mt-1';
          errorDiv.textContent = 'Please enter a valid phone number';
          field.parentElement.appendChild(errorDiv);
        }
      }
    });
    
    return isValid;
  }
  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    form.addEventListener("submit", function (e) {
      const btn = form.querySelector(".btn-with-loader");
      const hasCustomValidation = form.id === 'registerForm' || form.id === 'otpForm';
      
      if (!hasCustomValidation) {
        const isValid = validateForm(form);
        
        if (!isValid) {
          const firstError = form.querySelector('.is-invalid, .input-error');
          if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstError.focus();
          }
          
          return false;
        }
      }
      if (btn && btn.dataset.loading !== "true") {
        btn.dataset.loading = "true";
        if (!btn.dataset.originalText) {
          btn.dataset.originalText = btn.innerHTML;
        }
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';
        btn.disabled = true;
      }
    });
    const formFields = form.querySelectorAll('input, textarea, select');
    formFields.forEach((field) => {
      field.addEventListener('input', function () {
        this.classList.remove('is-invalid');
        this.classList.remove('input-error');
        const errorMessage = this.parentElement.querySelector('.field-error-message');
        if (errorMessage) {
          errorMessage.remove();
        }
        const existingErrorId = this.id + '_error';
        const existingError = document.getElementById(existingErrorId);
        if (existingError) {
          existingError.style.display = 'none';
        }
      });
    });
  });
  const standaloneButtons = document.querySelectorAll("button.btn-with-loader:not(form button)");
  standaloneButtons.forEach((btn) => {
    btn.addEventListener("click", function () {
      if (btn.dataset.loading === "true") return;
      
      btn.dataset.loading = "true";
      if (!btn.dataset.originalText) {
        btn.dataset.originalText = btn.innerHTML;
      }
      
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';
      btn.disabled = true;
    });
  });
  const loaderLinks = document.querySelectorAll("a .btn-with-loader");
  loaderLinks.forEach((icon) => {
    const link = icon.closest("a");
    link.addEventListener("click", function (e) {
      if (link.dataset.loading === "true") return;
      
      link.dataset.loading = "true";
      icon.textContent = "Loading...";
      e.preventDefault();
      
      setTimeout(() => {
        window.location.href = link.href;
      }, 300);
    });
  });
  window.resetFormLoader = function(form) {
    const btn = form.querySelector(".btn-with-loader");
    if (btn) {
      btn.dataset.loading = "false";
      btn.innerHTML = btn.dataset.originalText || 'Submit';
      btn.disabled = false;
    }
  };
  
});