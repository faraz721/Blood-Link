// BloodLink main JS - navbar toggle, floating buttons, helpers

document.addEventListener("DOMContentLoaded", () => {
  const hamburger = document.getElementById("hamburger");
  const mobileMenu = document.getElementById("mobileMenu");

  if (hamburger && mobileMenu) {
    hamburger.addEventListener("click", () => {
      mobileMenu.classList.toggle("open");
    });
    mobileMenu.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => mobileMenu.classList.remove("open"));
    });
  }

  // Auto-hide flash messages (~4s) + close (×) button
  document.querySelectorAll(".alert").forEach((el) => {
    if (!el.querySelector(".alert-close")) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "alert-close";
      btn.setAttribute("aria-label", "Close");
      btn.innerHTML = "&times;";
      btn.addEventListener("click", () => {
        el.classList.add("alert-hide");
        setTimeout(() => el.remove(), 300);
      });
      el.appendChild(btn);
    }
    setTimeout(() => {
      el.classList.add("alert-hide");
      setTimeout(() => el.remove(), 300);
    }, 4000);
  });

  // WhatsApp "same as phone" toggle
  // Default: WhatsApp field VISIBLE, checkbox UNCHECKED
  // When checked: hide WhatsApp field
  const sameCb = document.getElementById("whatsapp_same");
  const whatsappGroup = document.getElementById("whatsapp_group");
  if (sameCb && whatsappGroup) {
    const toggle = () => {
      whatsappGroup.style.display = sameCb.checked ? "none" : "block";
    };
    sameCb.addEventListener("change", toggle);
    toggle(); // apply initial state
  }

  // District -> Village cascade
  const districtSelect = document.getElementById("district");
  const villageSelect = document.getElementById("village_id");
  if (districtSelect && villageSelect) {
    const loadVillages = async (district) => {
      const current = villageSelect.value;
      villageSelect.innerHTML = '<option value="">Select Village / Area</option>';
      if (!district) return;
      try {
        const res = await fetch(`/api/locations?district=${encodeURIComponent(district)}`);
        const data = await res.json();
        data.forEach((v) => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = v.name;
          if (String(v.id) === String(current)) opt.selected = true;
          villageSelect.appendChild(opt);
        });
      } catch (e) {
        console.error("Failed to load villages", e);
      }
    };
    districtSelect.addEventListener("change", () => loadVillages(districtSelect.value));
    if (districtSelect.value) loadVillages(districtSelect.value);
  }
});