// Filters and count on the item list. Pages work without this script.
(function () {
  function pick(seg, btn) {
    seg.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b === btn)); });
  }

  var filters = document.querySelectorAll("[data-filter]");
  var count = document.getElementById("pcount");
  function applyFilters() {
    var want = {};
    filters.forEach(function (seg) { want[seg.dataset.filter] = seg.querySelector('[aria-pressed="true"]').dataset.value; });
    var shown = 0;
    document.querySelectorAll("#plist tbody tr").forEach(function (tr) {
      tr.hidden = Object.keys(want).some(function (k) { return want[k] !== "all" && tr.dataset[k] !== want[k]; });
      if (!tr.hidden) shown += 1;
    });
    if (count) count.textContent = "显示 " + shown + " 题";
  }
  filters.forEach(function (seg) {
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (b) { pick(seg, b); applyFilters(); }
    });
  });
})();
