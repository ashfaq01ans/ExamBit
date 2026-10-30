// Show/hide password. Each toggle button names its input in data-target.
document.querySelectorAll(".pw-toggle").forEach(function (button) {
  button.addEventListener("click", function () {
    var input = document.getElementById(button.dataset.target);
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    button.classList.toggle("is-visible", show);
    button.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
});
