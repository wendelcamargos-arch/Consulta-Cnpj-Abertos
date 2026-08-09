const pages = ['search', 'exports'];

const state = {
  activePage: 'dashboard',
  importRunning: false,
  logs: [
    'Sistema inicializado.',
    'Interface pronta para integração com a base oficial.',
  ],
  history: [
    {
      date: '09/07/2026',
      time: '09:12',
      startDate: '01/07/2026',
      endDate: '05/07/2026',
      uf: 'SP',
      municipio: 'São Paulo',
      quantity: 245,
      duration: '1.8s',
    },
    {
      date: '08/07/2026',
      time: '16:40',
      startDate: '20/06/2026',
      endDate: '25/06/2026',
      uf: 'RJ',
      municipio: 'Rio de Janeiro',
      quantity: 172,
      duration: '2.4s',
    },
  ],
  exports: [
    {
      name: 'empresa_sp_02072026.xlsx',
      date: '09/07/2026',
      time: '10:05',
      quantity: 320,
      format: 'Excel',
      status: 'Concluído',
    },
    {
      name: 'empresas_rj_08072026.csv',
      date: '09/07/2026',
      time: '11:19',
      quantity: 180,
      format: 'CSV',
      status: 'Concluído',
    },
  ],
  config: {
    maxDays: 10,
    maxRecords: 10000,
    baseFolder: '/dados/base_oficial',
    exportFolder: '/dados/export',
    theme: 'light',
    language: 'pt-BR',
  },
  search: {
    startDate: '',
    endDate: '',
    uf: '',
    municipio: '',
    bairro: '',
    cep: '',
    cnae: '',
    natureza: '',
    situacao: '',
    porte: '',
    capitalMin: '',
    capitalMax: '',
    empresaMatriz: false,
    empresaFilial: false,
    onlyPhone: false,
    onlyEmail: false,
    onlyWebsite: false,
    limit: 100,
  },
  searchTable: {
    filter: '',
    sortKey: 'razaoSocial',
    sortDirection: 'asc',
    page: 1,
    pageSize: 10,
    selected: new Set(),
  },
  searchResults: [],
};

// Colunas exibidas na grade de resultados. Mantidas em sincronia com o que o
// backend (SearchResult) realmente retorna, para não exibir colunas vazias.
const searchColumns = [
  { key: 'select', label: '', sortable: false, width: '44px' },
  { key: 'cnpj', label: 'CNPJ', sortable: true },
  { key: 'razaoSocial', label: 'Razão Social', sortable: true },
  { key: 'uf', label: 'UF', sortable: true },
  { key: 'municipio', label: 'Município', sortable: true },
  { key: 'situacaoCadastral', label: 'Situação Cadastral', sortable: true },
  { key: 'dataSituacao', label: 'Data da Situação', sortable: true },
];

const selectors = {
  pageTitle: document.getElementById('pageTitle'),
  pageHeading: document.getElementById('pageHeading'),
  sidebarLinks: document.querySelectorAll('.sidebar-link'),
  pagePanels: {
    dashboard: document.getElementById('dashboardPage'),
    search: document.getElementById('searchPage'),
    import: document.getElementById('importPage'),
    update: document.getElementById('updatePage'),
    history: document.getElementById('historyPage'),
    exports: document.getElementById('exportsPage'),
    status: document.getElementById('statusPage'),
    settings: document.getElementById('settingsPage'),
    logs: document.getElementById('logsPage'),
  },
  themeToggle: document.getElementById('themeToggle'),
  cardCompanies: document.getElementById('cardCompanies'),
  cardEstablishments: document.getElementById('cardEstablishments'),
  cardLastUpdate: document.getElementById('cardLastUpdate'),
  cardSearchCount: document.getElementById('cardSearchCount'),
  cardAverageTime: document.getElementById('cardAverageTime'),
  exportQuickButton: document.getElementById('exportQuickButton'),
  feedbackBanner: document.getElementById('feedbackBanner'),
};

// --- Status page actions ---
const fetchStatus = async () => {
  try {
    const res = await fetch('/test/status');
    const data = await res.json();
    if (!data.success) return;
    const meta = data.metadata || {};
    const stats = data.db_stats || {};
    selectors.statusVersion.textContent = meta.file_name || meta.url || '—';
    selectors.statusCompanies.textContent = (stats.total_companies || 0).toLocaleString();
    selectors.statusEstablishments.textContent = '—';
    selectors.statusImported.textContent = (stats.total_companies || 0).toLocaleString();
    selectors.statusDownloadTime.textContent = meta.time_s ? meta.time_s + 's' : '—';
    selectors.statusImportTime.textContent = '—';
    selectors.statusIndexTime.textContent = '—';
    selectors.statusDiskUsage.textContent = '—';
    selectors.statusOverall.textContent = 'Pronto';
  } catch (err) {
    console.error(err);
  }
};

const runTestPipeline = async () => {
  selectors.statusReport.textContent = 'Executando teste (modo seguro, sem download)...\n';
  try {
    const res = await fetch('/test/pipeline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({allow_download: false}),
    });
    const data = await res.json();
    if (!data.success) {
      selectors.statusReport.textContent += 'Falha: ' + JSON.stringify(data);
      return;
    }
    selectors.statusReport.textContent += JSON.stringify(data.report, null, 2);
    // refresh status
    fetchStatus();
  } catch (err) {
    selectors.statusReport.textContent += 'Erro: ' + err.toString();
  }
};

if (selectors.runTestButton) {
  selectors.runTestButton.addEventListener('click', () => runTestPipeline());
}

// Load status initially
fetchStatus();

const formatCurrency = (value) =>
  value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 2,
  });

const parseDateInput = (value) => {
  if (!value) return null;
  return new Date(value);
};

const searchPageMarkup = () => `
  <div class="card hero-card">
    <div class="section-header">
      <div>
        <h2>Consulta rápida</h2>
        <p>Use apenas o período desejado para gerar uma consulta confiável com a base oficial.</p>
      </div>
    </div>

    <div class="compact-filters">
      <div class="field-group">
        <label for="searchStartDate">Data Inicial</label>
        <input id="searchStartDate" type="date" />
      </div>
      <div class="field-group">
        <label for="searchEndDate">Data Final</label>
        <input id="searchEndDate" type="date" />
      </div>
      <div class="field-group">
        <label for="searchUf">UF</label>
        <input id="searchUf" type="text" maxlength="2" placeholder="SP" />
      </div>
      <div class="field-group">
        <label for="searchMunicipio">Município</label>
        <input id="searchMunicipio" type="text" placeholder="São Paulo" />
      </div>
      <div class="field-group">
        <label for="searchCnae">CNAE</label>
        <input id="searchCnae" type="text" placeholder="6201" />
      </div>
      <div class="field-group compact-actions">
        <button class="primary-button" id="applySearchButton">Pesquisar</button>
        <button class="secondary-button" id="resetSearchButton">Limpar</button>
      </div>
      <div class="field-group compact-actions">
        <button class="ghost-button" id="exportQuickButton">Exportar Excel</button>
      </div>
    </div>

    <div class="search-summary" id="searchSummary"></div>
    <div class="results-count" id="searchMatchCount"></div>

    <div class="section-header">
      <div>
        <h3>Resultados</h3>
        <p id="searchResultsMessage">Aguardando pesquisa.</p>
      </div>
    </div>

    <div class="table-wrapper">
      <table class="data-table" id="searchResultsTable"></table>
    </div>

    <div class="pagination" id="searchPagination"></div>
  </div>
`;

const exportPageMarkup = () => `
  <div class="card">
    <div class="section-header">
      <div>
        <h2>Exportações</h2>
        <p>Gere arquivos completos em Excel ou CSV a partir dos resultados.</p>
      </div>
    </div>

    <div class="export-toolbar">
      <div class="toolbar-group">
        <label for="exportFormat">Formato</label>
        <select id="exportFormat">
          <option value="Excel">Excel</option>
          <option value="CSV">CSV</option>
        </select>
      </div>
      <div class="toolbar-group">
        <button class="primary-button" id="exportSelectedButton">Exportar Selecionados</button>
        <button class="secondary-button" id="exportAllButton">Exportar Tudo</button>
      </div>
    </div>

    <div class="table-wrapper wide">
      <table class="dashboard-table" id="exportHistoryTable">
        <thead>
          <tr>
            <th>Nome do arquivo</th>
            <th>Data</th>
            <th>Hora</th>
            <th>Quantidade de empresas</th>
            <th>Formato</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="exportHistoryBody"></tbody>
      </table>
    </div>
  </div>
`;

const setSearchSelectors = () => {
  selectors.searchStartDate = document.getElementById('searchStartDate');
  selectors.searchEndDate = document.getElementById('searchEndDate');
  selectors.searchUf = document.getElementById('searchUf');
  selectors.searchMunicipio = document.getElementById('searchMunicipio');
  selectors.searchCnae = document.getElementById('searchCnae');
  selectors.searchLimit = document.getElementById('searchLimit');
  selectors.applySearchButton = document.getElementById('applySearchButton');
  selectors.resetSearchButton = document.getElementById('resetSearchButton');
  selectors.searchResultsTable = document.getElementById('searchResultsTable');
  selectors.searchPagination = document.getElementById('searchPagination');
  selectors.searchSummary = document.getElementById('searchSummary');
  selectors.searchResultsMessage = document.getElementById('searchResultsMessage');
  selectors.searchMatchCount = document.getElementById('searchMatchCount');
};

const setExportSelectors = () => {
  selectors.exportFormat = document.getElementById('exportFormat');
  selectors.exportSelectedButton = document.getElementById('exportSelectedButton');
  selectors.exportAllButton = document.getElementById('exportAllButton');
  selectors.exportHistoryBody = document.getElementById('exportHistoryBody');
};

const injectSearchPage = () => {
  selectors.pagePanels.search.innerHTML = searchPageMarkup();
  setSearchSelectors();
  updateSearchForm();
  renderSearchSummary();
  renderSearchTable();
  renderPagination();
  initSearchEvents();
};

const injectExportPage = () => {
  selectors.pagePanels.exports.innerHTML = exportPageMarkup();
  setExportSelectors();
  renderExportHistory();
  initExportEvents();
};

const updateSearchForm = () => {
  if (selectors.searchStartDate) selectors.searchStartDate.value = state.search.startDate;
  if (selectors.searchEndDate) selectors.searchEndDate.value = state.search.endDate;
  if (selectors.searchUf) selectors.searchUf.value = state.search.uf;
  if (selectors.searchMunicipio) selectors.searchMunicipio.value = state.search.municipio;
  if (selectors.searchCnae) selectors.searchCnae.value = state.search.cnae;
  if (selectors.searchLimit) selectors.searchLimit.value = state.search.limit;
};

const buildCard = (label, value) => `
  <article class="summary-card">
    <span>${label}</span>
    <strong>${value}</strong>
  </article>
`;

const renderSearchSummary = () => {
  const visible = filterSearchResults();
  const message = visible.length === 0 ? 'Nenhum resultado encontrado' : `${visible.length.toLocaleString('pt-BR')} resultado(s)`;
  if (selectors.searchSummary) {
    selectors.searchSummary.innerHTML = [
      buildCard('Quantidade encontrada', message),
      buildCard('Tempo da pesquisa', '≤ 1s'),
      buildCard('Tempo do servidor', '≤ 0.3s'),
      buildCard('Última atualização da base', '09/07/2026 11:32'),
    ].join('');
  }
  if (selectors.searchResultsMessage) {
    selectors.searchResultsMessage.textContent = visible.length === 0 ? 'Nenhum resultado encontrado para os filtros informados.' : 'Resultados disponíveis para visualização e exportação.';
  }
};

const compareValues = (a, b, direction, numeric) => {
  if (a == null) return 1;
  if (b == null) return -1;
  if (numeric) {
    return direction === 'asc' ? a - b : b - a;
  }
  const left = String(a).toLowerCase();
  const right = String(b).toLowerCase();
  if (left < right) return direction === 'asc' ? -1 : 1;
  if (left > right) return direction === 'asc' ? 1 : -1;
  return 0;
};

const sortResults = (rows) => {
  const { sortKey, sortDirection } = state.searchTable;
  if (!sortKey) return rows;
  const numericFields = [];
  return [...rows].sort((a, b) => compareValues(a[sortKey], b[sortKey], sortDirection, numericFields.includes(sortKey)));
};

// O backend (SearchService) já aplica todos os filtros no SQL, então a grade
// apenas exibe o que a API retornou — sem re-filtrar no cliente (o que poderia
// esconder registros válidos).
const filterSearchResults = () => state.searchResults;

const isValidDate = (dateObj) => dateObj instanceof Date && !Number.isNaN(dateObj.getTime());

const validateSearchForm = () => {
  const { startDate, endDate, limit } = state.search;

  if (!startDate) {
    showFeedback('Data inicial obrigatória.');
    return false;
  }

  if (!endDate) {
    showFeedback('Data final obrigatória.');
    return false;
  }

  const start = parseDateInput(startDate);
  const end = parseDateInput(endDate);

  if (!isValidDate(start) || !isValidDate(end)) {
    showFeedback('Datas inválidas. Verifique o início e o fim.');
    return false;
  }

  const diffDays = Math.floor((end - start) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) {
    showFeedback('Data final não pode ser menor que a data inicial.');
    return false;
  }

  if (diffDays > state.config.maxDays) {
    showFeedback(`O período de pesquisa não pode ultrapassar ${state.config.maxDays} dias.`);
    return false;
  }

  const limitValue = Number(limit);
  if (!limitValue || limitValue <= 0) {
    showFeedback('Limite de resultados obrigatório.');
    return false;
  }

  return true;
};

const renderSearchTable = () => {
  if (!selectors.searchResultsTable) return;
  const filtered = sortResults(filterSearchResults());
  const limit = Number(state.search.limit);
  const limited = filtered.slice(0, limit);
  const totalPages = Math.max(1, Math.ceil(limited.length / state.searchTable.pageSize));
  if (state.searchTable.page > totalPages) state.searchTable.page = totalPages;
  const start = (state.searchTable.page - 1) * state.searchTable.pageSize;
  const pageRows = limited.slice(start, start + state.searchTable.pageSize);

  const header = searchColumns
    .map((column) => {
      if (column.key === 'select') {
        return `<th class="checkbox-cell"><input type="checkbox" id="searchSelectAllRows" /></th>`;
      }
      return `
        <th data-key="${column.key}" class="${column.sortable ? 'sortable' : ''}">
          ${column.label}
          ${column.sortable ? `<span class="sort-indicator">${state.searchTable.sortKey === column.key ? (state.searchTable.sortDirection === 'asc' ? '▲' : '▼') : ''}</span>` : ''}
        </th>
      `;
    })
    .join('');

  const dataColumns = searchColumns.filter((column) => column.key !== 'select');
  const rows = pageRows
    .map((row) => {
      const isChecked = state.searchTable.selected.has(row.cnpj);
      const cells = dataColumns
        .map((column) => `<td>${row[column.key] ?? '-'}</td>`)
        .join('');
      return `
        <tr>
          <td class="checkbox-cell"><input type="checkbox" class="row-checkbox" data-cnpj="${row.cnpj}" ${isChecked ? 'checked' : ''} /></td>
          ${cells}
        </tr>
      `;
    })
    .join('');

  selectors.searchResultsTable.innerHTML = `
    <thead>
      <tr>${header}</tr>
    </thead>
    <tbody>${rows}</tbody>
  `;

  const selectAllCheckbox = document.getElementById('searchSelectAllRows');
  if (selectAllCheckbox) {
    selectAllCheckbox.checked = pageRows.length > 0 && pageRows.every((row) => state.searchTable.selected.has(row.cnpj));
    selectAllCheckbox.addEventListener('change', (event) => {
      const checked = event.target.checked;
      pageRows.forEach((row) => {
        if (checked) {
          state.searchTable.selected.add(row.cnpj);
        } else {
          state.searchTable.selected.delete(row.cnpj);
        }
      });
      renderSearchTable();
    });
  }

  document.querySelectorAll('#searchResultsTable th.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (!key) return;
      if (state.searchTable.sortKey === key) {
        state.searchTable.sortDirection = state.searchTable.sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        state.searchTable.sortKey = key;
        state.searchTable.sortDirection = 'asc';
      }
      renderSearchTable();
    });
  });

  document.querySelectorAll('.row-checkbox').forEach((checkbox) => {
    checkbox.addEventListener('change', (event) => {
      const cnpj = event.target.dataset.cnpj;
      if (!cnpj) return;
      if (event.target.checked) {
        state.searchTable.selected.add(cnpj);
      } else {
        state.searchTable.selected.delete(cnpj);
      }
      renderSearchTable();
    });
  });

  if (selectors.searchMatchCount) {
    selectors.searchMatchCount.textContent = `${limited.length.toLocaleString('pt-BR')} registro(s) encontrados`;
  }
  renderPagination(limited.length);
};

const renderPagination = (totalItems) => {
  if (!selectors.searchPagination) return;
  const total = totalItems ?? filterSearchResults().length;
  const limit = Number(state.search.limit);
  const totalPages = Math.max(1, Math.ceil(Math.min(total, limit) / state.searchTable.pageSize));
  const current = state.searchTable.page;

  const pages = [];
  const range = 2;
  const start = Math.max(1, current - range);
  const end = Math.min(totalPages, current + range);

  if (current > 1) {
    pages.push(`<button data-page="${current - 1}">Anterior</button>`);
  }

  for (let page = start; page <= end; page += 1) {
    pages.push(`
      <button data-page="${page}" class="${page === current ? 'active' : ''}">${page}</button>
    `);
  }

  if (current < totalPages) {
    pages.push(`<button data-page="${current + 1}">Próximo</button>`);
  }

  selectors.searchPagination.innerHTML = `
    <div class="pages">${pages.join('')}</div>
    <div>${current} de ${totalPages} páginas</div>
  `;

  selectors.searchPagination.querySelectorAll('button').forEach((button) => {
    button.addEventListener('click', () => {
      state.searchTable.page = Number(button.dataset.page);
      renderSearchTable();
    });
  });
};

const updateSearchState = () => {
  if (selectors.searchStartDate) state.search.startDate = selectors.searchStartDate.value;
  if (selectors.searchEndDate) state.search.endDate = selectors.searchEndDate.value;
  if (selectors.searchUf) state.search.uf = selectors.searchUf.value;
  if (selectors.searchMunicipio) state.search.municipio = selectors.searchMunicipio.value;
  if (selectors.searchCnae) state.search.cnae = selectors.searchCnae.value;
  if (selectors.searchLimit) state.search.limit = selectors.searchLimit.value;
};

// Mapeia a linha da API (SearchResult) para as colunas exibidas. Só os campos
// que o backend realmente entrega.
const mapApiSearchResult = (row) => ({
  cnpj: row.cnpj || '',
  razaoSocial: row.nome || '',
  uf: row.uf || '',
  municipio: row.municipio || '',
  situacaoCadastral: row.situacao || '',
  dataSituacao: row.data_situacao || '',
});

const loadSearchResultsFromApi = async () => {
  updateSearchState();
  if (!validateSearchForm()) return false;

  try {
    const payload = {
      start_date: state.search.startDate,
      end_date: state.search.endDate,
      uf: state.search.uf || undefined,
      municipio: state.search.municipio || undefined,
      cnae: state.search.cnae || undefined,
      limit: Number(state.search.limit || 100),
      page: 1,
      page_size: Number(state.search.limit || 100),
    };

    const response = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
      showFeedback(data.message || 'Erro ao consultar a base.');
      return false;
    }

    state.searchResults = (data.results || []).map(mapApiSearchResult);
    state.searchTable.page = 1;
    renderSearchSummary();
    renderSearchTable();
    showFeedback(data.message || 'Pesquisa concluída.');
    return true;
  } catch (error) {
    console.error(error);
    showFeedback('Erro ao consultar a base.');
    return false;
  }
};

const applySearch = async () => {
  await loadSearchResultsFromApi();
};

const resetSearch = () => {
  state.search = {
    ...state.search,
    startDate: '',
    endDate: '',
    uf: '',
    municipio: '',
    bairro: '',
    cep: '',
    cnae: '',
    natureza: '',
    situacao: '',
    porte: '',
    capitalMin: '',
    capitalMax: '',
    empresaMatriz: false,
    empresaFilial: false,
    onlyPhone: false,
    onlyEmail: false,
    onlyWebsite: false,
    limit: 100,
  };
  state.searchTable.filter = '';
  state.searchTable.page = 1;
  state.searchTable.selected.clear();
  state.searchResults = [];
  updateSearchForm();
  renderSearchSummary();
  renderSearchTable();
};

const toggleSelectAll = () => {
  const filtered = sortResults(filterSearchResults()).slice(0, Number(state.search.limit));
  const start = (state.searchTable.page - 1) * state.searchTable.pageSize;
  const pageRows = filtered.slice(start, start + state.searchTable.pageSize);
  const allSelected = pageRows.length > 0 && pageRows.every((row) => state.searchTable.selected.has(row.cnpj));

  pageRows.forEach((row) => {
    if (allSelected) {
      state.searchTable.selected.delete(row.cnpj);
    } else {
      state.searchTable.selected.add(row.cnpj);
    }
  });
  renderSearchTable();
};

const initSearchEvents = () => {
  if (selectors.applySearchButton) {
    selectors.applySearchButton.addEventListener('click', () => applySearch());
  }
  if (selectors.resetSearchButton) {
    selectors.resetSearchButton.addEventListener('click', resetSearch);
  }
  if (selectors.searchLimit) {
    selectors.searchLimit.addEventListener('change', () => {
      updateSearchState();
      state.searchTable.page = 1;
      renderSearchTable();
    });
  }
};

const renderExportHistory = () => {
  if (!selectors.exportHistoryBody) return;
  selectors.exportHistoryBody.innerHTML = state.exports
    .map(
      (item) => `
        <tr>
          <td>${item.name}</td>
          <td>${item.date}</td>
          <td>${item.time}</td>
          <td>${item.quantity}</td>
          <td>${item.format}</td>
          <td>${item.status}</td>
        </tr>
      `,
    )
    .join('');
};

const buildExportData = () => {
  const filtered = sortResults(filterSearchResults()).slice(0, Number(state.search.limit));
  const selected = Array.from(state.searchTable.selected);
  if (selected.length > 0) {
    return filtered.filter((row) => selected.includes(row.cnpj));
  }
  return filtered;
};

const downloadFile = (content, filename, type) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
};

const exportToCsv = (rows, filename) => {
  const headers = searchColumns.filter((column) => column.key !== 'select').map((column) => `"${column.label}"`).join(',');
  const body = rows
    .map((row) =>
      searchColumns
        .filter((column) => column.key !== 'select')
        .map((column) => `"${String(row[column.key] ?? '').replace(/"/g, '""')}"`)
        .join(',')
    )
    .join('\n');
  downloadFile(`${headers}\n${body}`, `${filename}.csv`, 'text/csv;charset=utf-8;');
};

const exportToExcel = (rows, filename) => {
  const headers = searchColumns.filter((column) => column.key !== 'select').map((column) => column.label).join('\t');
  const body = rows
    .map((row) =>
      searchColumns
        .filter((column) => column.key !== 'select')
        .map((column) => row[column.key] ?? '')
        .join('\t')
    )
    .join('\n');
  downloadFile(`${headers}\n${body}`, `${filename}.xls`, 'application/vnd.ms-excel');
};

const exportResults = async (format) => {
  updateSearchState();
  if (!validateSearchForm()) return;

  const params = new URLSearchParams({
    start_date: state.search.startDate,
    end_date: state.search.endDate,
    uf: state.search.uf || '',
    municipio: state.search.municipio || '',
    limit: String(state.search.limit || 100),
  });

  const endpoint = format === 'CSV' ? `/export/csv?${params.toString()}` : `/export/excel?${params.toString()}`;

  try {
    const response = await fetch(endpoint);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      showFeedback(errorData.message || 'Erro ao exportar.');
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `cnpj_hunter_export_${new Date().toISOString().slice(0, 10)}.${format === 'CSV' ? 'csv' : 'xlsx'}`;
    anchor.click();
    URL.revokeObjectURL(url);
    showFeedback(`Exportação ${format} gerada com sucesso.`);
  } catch (error) {
    console.error(error);
    showFeedback('Erro ao exportar.');
  }
};

const initExportEvents = () => {
  if (selectors.exportSelectedButton) {
    selectors.exportSelectedButton.addEventListener('click', () => exportResults(selectors.exportFormat.value));
  }
  if (selectors.exportAllButton) {
    selectors.exportAllButton.addEventListener('click', () => {
      state.searchTable.selected.clear();
      renderSearchTable();
      exportResults(selectors.exportFormat.value);
    });
  }
};

const updateDashboard = () => {
  selectors.cardCompanies.textContent = '1.280.000';
  selectors.cardEstablishments.textContent = '4.560.000';
  selectors.cardLastUpdate.textContent = '09/07/2026 11:32';
  selectors.cardSearchCount.textContent = '428';
  selectors.cardAverageTime.textContent = '1.9s';
};

const updateImportInfo = () => {
  selectors.importLastUpdate.textContent = '09/07/2026 11:32';
  selectors.importCompanies.textContent = '1.280.000';
  selectors.importEstablishments.textContent = '4.560.000';
  selectors.importDuration.textContent = '18m 32s';
  selectors.importStatus.textContent = 'Base pronta';
  selectors.importLog.textContent = state.logs.join('\n');
  selectors.importProgress.style.width = '100%';
};

const updateHistory = () => {
  selectors.historyBody.innerHTML = state.history
    .map(
      (item) => `
        <tr>
          <td>${item.date}</td>
          <td>${item.time}</td>
          <td>${item.startDate}</td>
          <td>${item.endDate}</td>
          <td>${item.uf}</td>
          <td>${item.municipio}</td>
          <td>${item.quantity}</td>
          <td>${item.duration}</td>
        </tr>
      `,
    )
    .join('');
};

const updateSettings = () => {
  selectors.maxDays.value = state.config.maxDays;
  selectors.maxRecords.value = state.config.maxRecords;
  selectors.baseFolder.value = state.config.baseFolder;
  selectors.exportFolder.value = state.config.exportFolder;
  selectors.uiTheme.value = state.config.theme;
  selectors.language.value = state.config.language;
};

const updateLogs = () => {
  selectors.systemLogs.textContent = state.logs.join('\n');
};

const showFeedback = (message) => {
  selectors.feedbackBanner.textContent = message;
  selectors.feedbackBanner.classList.add('show');
  clearTimeout(selectors.feedbackBanner.timeout);
  selectors.feedbackBanner.timeout = setTimeout(() => {
    selectors.feedbackBanner.classList.remove('show');
  }, 2600);
};

const setPage = (pageKey) => {
  state.activePage = pageKey;
  const titleMap = {
    dashboard: 'Dashboard',
    search: 'Pesquisar Empresas',
    import: 'Importar Base Receita',
    update: 'Atualização',
    exports: 'Exportações',
    history: 'Histórico',
    settings: 'Configurações',
    logs: 'Logs',
  };

  selectors.pageTitle.textContent = titleMap[pageKey];
  selectors.pageHeading.textContent = titleMap[pageKey];

  Object.entries(selectors.pagePanels).forEach(([key, panel]) => {
    panel.classList.toggle('hidden', key !== pageKey);
  });

  selectors.sidebarLinks.forEach((button) => {
    button.classList.toggle('active', button.dataset.page === pageKey);
  });
};

const applyConfigChanges = () => {
  state.config.maxDays = Number(selectors.maxDays.value);
  state.config.maxRecords = Number(selectors.maxRecords.value);
  state.config.baseFolder = selectors.baseFolder.value;
  state.config.exportFolder = selectors.exportFolder.value;
  state.config.theme = selectors.uiTheme.value;
  state.config.language = selectors.language.value;

  document.body.classList.toggle('theme-dark', state.config.theme === 'dark');
  document.body.classList.toggle('theme-light', state.config.theme === 'light');
  selectors.themeToggle.textContent = state.config.theme === 'dark' ? 'Modo Claro' : 'Modo Escuro';
  showFeedback('Configurações salvas com sucesso.');
};

const resetConfig = () => {
  state.config = {
    maxDays: 10,
    maxRecords: 10000,
    baseFolder: '/dados/base_oficial',
    exportFolder: '/dados/export',
    theme: 'light',
    language: 'pt-BR',
  };
  updateSettings();
  applyConfigChanges();
  showFeedback('Configurações restauradas aos valores padrão.');
};

const addLog = (message) => {
  const timestamp = new Date().toLocaleString('pt-BR');
  state.logs.unshift(`[${timestamp}] ${message}`);
  updateLogs();
};

const simulateImport = (action) => {
  if (state.importRunning) {
    showFeedback('Uma ação de importação já está em andamento.');
    return;
  }

  state.importRunning = true;
  selectors.importStatus.textContent = `${action} em progresso`;
  selectors.importProgress.style.width = '0%';
  selectors.importLog.textContent = '';
  let progress = 0;

  const interval = setInterval(() => {
    progress += 10;
    selectors.importProgress.style.width = `${progress}%`;
    selectors.importLog.textContent += `${action}... ${progress}% concluído.
`;
    addLog(`${action} - ${progress}%`);

    if (progress >= 100) {
      clearInterval(interval);
      state.importRunning = false;
      selectors.importStatus.textContent = 'Base atualizada';
      selectors.importLastUpdate.textContent = new Date().toLocaleString('pt-BR');
      selectors.importDuration.textContent = '19m 12s';
      addLog(`${action} concluído com sucesso.`);
      updateImportInfo();
      showFeedback(`${action} concluído.`);
    }
  }, 220);
};

const initNavigation = () => {
  selectors.sidebarLinks.forEach((link) => {
    link.addEventListener('click', () => setPage(link.dataset.page));
  });
};

const initActions = () => {
  if (selectors.exportQuickButton) {
    selectors.exportQuickButton.addEventListener('click', async () => {
      updateSearchState();
      if (!validateSearchForm()) return;
      await exportResults('Excel');
      setPage('exports');
    });
  }
};

const init = () => {
  state.searchResults = [];
  injectSearchPage();
  injectExportPage();
  initNavigation();
  initActions();
  setPage('search');
};

window.addEventListener('load', init);
