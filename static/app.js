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