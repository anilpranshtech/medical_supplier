document.addEventListener("DOMContentLoaded", function () {
    const forms = document.querySelectorAll("form");
    forms.forEach((form) => {
      form.addEventListener("submit", function () {
        const btn = form.querySelector(".btn-with-loader");
        if (!btn || btn.dataset.loading === "true") return;
        btn.dataset.loading = "true";
        btn.innerHTML = "Loading...";
        btn.disabled = true;
      });
    });
    const standaloneButtons = document.querySelectorAll("button.btn-with-loader:not(form button)");
    standaloneButtons.forEach((btn) => {
      btn.addEventListener("click", function () {
        if (btn.dataset.loading === "true") return;
        btn.dataset.loading = "true";
        btn.innerHTML = "Loading...";
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
  });
  