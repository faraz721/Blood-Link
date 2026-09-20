document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("searchForm");
  const resultsEl = document.getElementById("searchResults");
  const countEl = document.getElementById("resultCount");

  if (!form) return;

  const doSearch = async (mode = "normal") => {
    const blood_group = document.getElementById("blood_group").value;
    const district = document.getElementById("district").value;
    const village_id = document.getElementById("village_id").value;

    if (!blood_group) {
      countEl.textContent = "";
      resultsEl.innerHTML = '<p class="alert alert-warning">Please select a blood group to search.</p>';
      return;
    }

    resultsEl.innerHTML = '<p class="form-hint">Searching...</p>';

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blood_group, district, village_id, mode }),
      });
      const data = await res.json();
      countEl.textContent = `${data.count} donor(s) found`;

      if (!data.donors.length) {
        resultsEl.innerHTML = '<p class="form-hint">No available donors match your criteria.</p>';
        return;
      }

      resultsEl.innerHTML = data.donors
        .map(
          (d) => `
        <div class="card donor-card">
          <span class="blood-badge">${d.blood_group}</span>
          <h3 style="margin:0.3rem 0">${escapeHtml(d.name)}</h3>
          <p class="meta"><strong>District:</strong> ${escapeHtml(d.district)}</p>
          <p class="meta"><strong>Village:</strong> ${escapeHtml(d.village)}</p>
          <p class="meta"><strong>Status:</strong> ${escapeHtml(d.availability)}</p>
          <div class="donor-actions">
            <a class="btn btn-primary btn-sm" href="tel:${d.phone}">Call</a>
            <a class="btn btn-outline btn-sm" href="https://wa.me/92${d.whatsapp.replace(/^0/, '')}" target="_blank" rel="noopener">WhatsApp</a>
          </div>
        </div>`
        )
        .join("");
    } catch (e) {
      resultsEl.innerHTML = '<p class="alert alert-danger">Search failed. Please try again.</p>';
    }
  };

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    doSearch("normal");
  });

  document.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => doSearch(btn.dataset.mode));
  });

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
});
