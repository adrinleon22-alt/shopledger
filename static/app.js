async function loadDashboard() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const currentMonth = `${year}-${month}`;

  document.getElementById("month-label").textContent = currentMonth;

  try {
    const response = await fetch(`/summary?month=${currentMonth}`);
    
    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    const data = await response.json();

    document.getElementById("total-sales").textContent = `₹${data.total_sales}`;
    document.getElementById("total-expenses").textContent = `₹${data.total_expenses}`;
    document.getElementById("profit").textContent = `₹${data.profit}`;
    document.getElementById("udhaar").textContent = "—";
  } catch (error) {
    console.error("Failed to load dashboard:", error);
  }
}

loadDashboard();