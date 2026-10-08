(() => {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("aqa-theme");
  if (savedTheme) root.setAttribute("data-bs-theme", savedTheme);
  if (toggle) {
    toggle.addEventListener("click", () => {
      const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-bs-theme", next);
      localStorage.setItem("aqa-theme", next);
    });
  }

  const input = document.getElementById("assignment");
  const drop = document.getElementById("dropzone");
  const form = document.getElementById("upload-form");
  const selected = document.getElementById("selected-file");
  if (input && drop) {
    const showFile = (file) => {
      if (selected) selected.textContent = file ? `${file.name} (${Math.ceil(file.size / 1024)} KB)` : "";
    };
    input.addEventListener("change", () => showFile(input.files[0]));
    ["dragenter", "dragover"].forEach((name) => drop.addEventListener(name, (event) => {
      event.preventDefault();
      drop.classList.add("drag-active");
    }));
    ["dragleave", "drop"].forEach((name) => drop.addEventListener(name, (event) => {
      event.preventDefault();
      drop.classList.remove("drag-active");
    }));
    drop.addEventListener("drop", (event) => {
      const files = event.dataTransfer.files;
      if (files.length) {
        input.files = files;
        showFile(files[0]);
      }
    });
  }
  if (form) {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!input.files.length) {
        input.reportValidity();
        return;
      }
      const progress = document.getElementById("upload-progress");
      const bar = document.getElementById("progress-bar");
      const button = document.getElementById("submit-button");
      const xhr = new XMLHttpRequest();
      xhr.open("POST", form.action);
      xhr.upload.addEventListener("progress", (uploadEvent) => {
        if (uploadEvent.lengthComputable) {
          const percent = Math.round(uploadEvent.loaded / uploadEvent.total * 100);
          progress.classList.remove("d-none");
          progress.setAttribute("aria-valuenow", percent);
          bar.style.width = `${percent}%`;
          bar.textContent = `${percent}%`;
        }
      });
      xhr.addEventListener("load", () => {
        if (xhr.responseURL) window.location.assign(xhr.responseURL);
        else window.location.reload();
      });
      xhr.addEventListener("error", () => {
        button.disabled = false;
        button.textContent = "Upload failed — try again";
      });
      button.disabled = true;
      button.textContent = "Analyzing…";
      progress.classList.remove("d-none");
      xhr.send(new FormData(form));
    });
  }
})();
