// ─── Toast ────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const el = document.getElementById('toast');
  const msgEl = document.getElementById('toastMsg');
  if (!el || !msgEl) return;
  msgEl.textContent = msg;
  el.className = `toast align-items-center text-white border-0 bg-${type}`;
  bootstrap.Toast.getOrCreateInstance(el, { delay: 3000 }).show();
}

// ─── Export Excel ─────────────────────────────────────────────────
function exportReport(period) {
  const a = document.createElement('a');
  a.href = `/api/period/${encodeURIComponent(period)}/report`;
  a.click();
}

// ─── Sidebar toggle ───────────────────────────────────────────────
document.getElementById('sidebarToggle')?.addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('collapsed');
});

// ─── Production ───────────────────────────────────────────────────
async function addProduct(period) {
  const body = {
    name:          document.getElementById('pName').value.trim(),
    unit:          document.getElementById('pUnit').value.trim() || 'шт',
    plan_qty:      document.getElementById('pPlanQty').value,
    fact_qty:      document.getElementById('pFactQty').value,
    cost_per_unit: document.getElementById('pCost').value,
  };
  if (!body.name) { showToast('Укажите название', 'danger'); return; }
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/product`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  if (r.ok) { showToast('Продукт сохранён'); setTimeout(() => location.reload(), 800); }
  else showToast('Ошибка сохранения', 'danger');
}

async function delProduct(period, name, btn) {
  if (!confirm(`Удалить «${name}»?`)) return;
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/product/${encodeURIComponent(name)}`, { method: 'DELETE' });
  if (r.ok) { btn.closest('tr').remove(); showToast('Удалено'); }
  else showToast('Ошибка удаления', 'danger');
}

// ─── Expenses ─────────────────────────────────────────────────────
async function addExpense(period) {
  const body = {
    category:    document.getElementById('eCat').value,
    name:        document.getElementById('eName').value.trim(),
    plan_amount: document.getElementById('ePlan').value,
    fact_amount: document.getElementById('eFact').value,
  };
  if (!body.name) { showToast('Укажите статью', 'danger'); return; }
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/expense`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  if (r.ok) { showToast('Сохранено'); setTimeout(() => location.reload(), 800); }
  else showToast('Ошибка', 'danger');
}

async function delExpense(period, cat, name, btn) {
  if (!confirm(`Удалить «${name}»?`)) return;
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/expense/${cat}/${encodeURIComponent(name)}`, { method: 'DELETE' });
  if (r.ok) { btn.closest('tr').remove(); showToast('Удалено'); }
  else showToast('Ошибка', 'danger');
}

// ─── Revenue ──────────────────────────────────────────────────────
async function addRevenue(period) {
  const body = {
    product: document.getElementById('rProduct').value.trim(),
    price:   document.getElementById('rPrice').value,
    qty:     document.getElementById('rQty').value,
  };
  if (!body.product) { showToast('Укажите продукт', 'danger'); return; }
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/revenue`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  if (r.ok) { showToast('Сохранено'); setTimeout(() => location.reload(), 800); }
  else showToast('Ошибка', 'danger');
}

async function delRevenue(period, product, btn) {
  if (!confirm(`Удалить «${product}»?`)) return;
  const r = await fetch(`/api/period/${encodeURIComponent(period)}/revenue/${encodeURIComponent(product)}`, { method: 'DELETE' });
  if (r.ok) { btn.closest('tr').remove(); showToast('Удалено'); }
  else showToast('Ошибка', 'danger');
}

// ─── Charts ───────────────────────────────────────────────────────
async function loadCharts(period) {
  const resp = await fetch(`/api/period/${encodeURIComponent(period)}/charts`);
  const d = await resp.json();

  const COLORS = ['#2563eb','#f97316','#22c55e','#a855f7','#ef4444','#06b6d4'];

  if (document.getElementById('expenseChart')) {
    new Chart(document.getElementById('expenseChart'), {
      type: 'doughnut',
      data: {
        labels: d.expense.labels,
        datasets: [{ data: d.expense.values, backgroundColor: COLORS, borderWidth: 2 }]
      },
      options: { plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } }, cutout: '60%' }
    });
  }

  if (document.getElementById('prodChart')) {
    new Chart(document.getElementById('prodChart'), {
      type: 'bar',
      data: {
        labels: d.production.labels,
        datasets: [
          { label: 'План', data: d.production.plan, backgroundColor: '#bfdbfe' },
          { label: 'Факт', data: d.production.fact, backgroundColor: '#2563eb' },
        ]
      },
      options: {
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true, grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } }
      }
    });
  }

  if (document.getElementById('pnlChart')) {
    const vals = d.pnl.values;
    const colors = vals.map(v => v >= 0 ? '#22c55e' : '#ef4444');
    new Chart(document.getElementById('pnlChart'), {
      type: 'bar',
      data: {
        labels: d.pnl.labels,
        datasets: [{ data: vals, backgroundColor: colors, borderRadius: 6 }]
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } }
      }
    });
  }
}
