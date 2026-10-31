// Show the course and session fields only when the role is "student".
(function () {
  var role = document.getElementById("role");
  var box = document.getElementById("student-fields");
  if (!role || !box) return;

  function update() {
    box.hidden = role.value !== "student";
  }

  role.addEventListener("change", update);
  update();
})();
