async function loadDashboard() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const currentMonth = `${year}-${month}`;

  document.getElementById("month-label").textContent = currentMonth;

  try {
    const [summaryResponse, udhaarResponse] = await Promise.all([
      fetch(`/summary?month=${currentMonth}`),
      fetch("/udhaar/total"),
    ]);

    if (!summaryResponse.ok || !udhaarResponse.ok) {
      throw new Error("One or more API calls failed");
    }

    const summary = await summaryResponse.json();
    const udhaar = await udhaarResponse.json();

    document.getElementById("total-sales").textContent = `₹${summary.total_sales}`;
    document.getElementById("total-expenses").textContent = `₹${summary.total_expenses}`;
    document.getElementById("profit").textContent = `₹${summary.profit}`;
    document.getElementById("udhaar").textContent = `₹${udhaar.total_udhaar}`;
  } catch (error) {
    console.error("Failed to load dashboard:", error);
  }
}

loadDashboard();

function openModal(modalId) {
  document.getElementById(modalId).classList.remove("hidden");
}

function closeModal(modalId) {
  document.getElementById(modalId).classList.add("hidden");
  document.getElementById(modalId).querySelectorAll(".error").forEach(el => {
    el.textContent = "";
  });
  document.getElementById(modalId).querySelectorAll("form").forEach(form => {
    form.reset();
  });
}

document.getElementById("open-sale-modal").addEventListener("click", () => {
  openModal("sale-modal");
});

document.getElementById("open-expense-modal").addEventListener("click", () => {
  openModal("expense-modal");
});

document.querySelectorAll(".close-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    closeModal(btn.dataset.modal);
  });
});

document.querySelectorAll(".modal").forEach(modal => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      closeModal(modal.id);
    }
  });
});
async function submitForm(formId, endpoint, modalId, errorPrefix) {
  const form = document.getElementById(formId);
  
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    form.querySelectorAll(".error").forEach(el => el.textContent = "");

    const formData = new FormData(form);
    const body = {};
    for (const [key, value] of formData.entries()) {
      if (value === "") continue;
      if (key === "quantity" || key === "customer_id") {
        body[key] = parseInt(value, 10);
      } else if (key === "price" || key === "amount") {
        body[key] = parseFloat(value);
      } else {
        body[key] = value;
      }
    }

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        closeModal(modalId);
        loadDashboard();
        return;
      }

      const errorData = await response.json();

      if (Array.isArray(errorData.detail)) {
        for (const err of errorData.detail) {
          const fieldName = err.loc[err.loc.length - 1];
          const errorEl = document.getElementById(`${errorPrefix}-${fieldName}-error`);
          if (errorEl) errorEl.textContent = err.msg;
        }
      } else {
        const firstError = form.querySelector(".error");
        if (firstError) firstError.textContent = errorData.detail || "Something went wrong";
      }
    } catch (error) {
      console.error("Submit failed:", error);
      const firstError = form.querySelector(".error");
      if (firstError) firstError.textContent = "Network error. Please try again.";
    }
  });
}

submitForm("sale-form", "/sales", "sale-modal", "sale");
submitForm("expense-form", "/expenses", "expense-modal", "expense");