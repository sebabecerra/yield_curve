import {
  LEGACY_ALIASES,
  RATE_MONTHS,
  fitNelsonSiegel,
  fitSvensson,
  naturalCubicSpline,
  reconstructNelsonSiegelCurve,
  reconstructSvenssonCurve,
} from "./models.js";
import { MARKET_ROWS } from "./market_rows.js";

const DEFAULT_COLUMNS = ["SPC_2Y", "SPC_3Y", "SPC_4Y", "SPC_5Y", "SPC_10Y"];
const LANG = document.documentElement.lang?.toLowerCase().startsWith("en") ? "en" : "es";
const ACCESS_STORAGE_KEY = "yield_curve_access_email";
const I18N = {
  es: {
    accessInvalid: "Ingresa un email válido para continuar.",
    accessStored: "Email actualizado.",
    comparePlaceholder: "Ingrese fecha para comparar",
    loadedRows: "Filas cargadas",
    series: "Series",
    estimatedPrefix: "Estimada",
    observedPrefix: "Observada",
    maturityMonths: "Madurez (meses)",
    rate: "Tasa",
    date: "Fecha",
    factor: "Factor",
    observedRate: "Tasa observada",
    selectAtLeast3: "Selecciona al menos 3 tasas.",
    selectAtLeast4: "Selecciona al menos 4 tasas.",
    noCompleteDates: "No hay fechas completas para las columnas elegidas.",
    chartUpdated: "Grafico actualizado.",
    loadedBase: (rows, firstDate, lastDate, count) =>
      `Base real cargada: ${rows} filas, desde ${firstDate} hasta ${lastDate}. Fechas completas para el set base: ${count}.`,
    emptyBase: "La base integrada viene vacia o no se pudo parsear.",
    failedLoad: "Fallo la carga de la base integrada.",
  },
  en: {
    accessInvalid: "Enter a valid email to continue.",
    accessStored: "Email updated.",
    comparePlaceholder: "Add comparison date",
    loadedRows: "Loaded rows",
    series: "Series",
    estimatedPrefix: "Estimated",
    observedPrefix: "Observed",
    maturityMonths: "Maturity (months)",
    rate: "Yield",
    date: "Date",
    factor: "Factor",
    observedRate: "Observed yield",
    selectAtLeast3: "Select at least 3 rates.",
    selectAtLeast4: "Select at least 4 rates.",
    noCompleteDates: "No complete dates are available for the selected columns.",
    chartUpdated: "Chart updated.",
    loadedBase: (rows, firstDate, lastDate, count) =>
      `Embedded market dataset loaded: ${rows} rows, from ${firstDate} to ${lastDate}. Complete dates for the base set: ${count}.`,
    emptyBase: "The embedded dataset is empty or could not be parsed.",
    failedLoad: "The embedded dataset could not be loaded.",
  },
};
const TEXT = I18N[LANG];
const state = {
  rows: [],
  accessEmail: "",
  availableDates: {
    ns: [],
    sv: [],
    sp: [],
  },
  calculations: {
    ns: null,
    sv: null,
    sp: null,
  },
};

function setGlobalStatus(text) {
  const el = document.getElementById("globalStatus");
  if (el) el.textContent = text;
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

function unlockAccess(email) {
  state.accessEmail = email.trim();
  localStorage.setItem(ACCESS_STORAGE_KEY, state.accessEmail);
  document.body.classList.remove("access-locked");
  document.getElementById("accessOverlay")?.classList.add("hidden");
  const sessionEmail = document.getElementById("sessionEmail");
  if (sessionEmail) sessionEmail.textContent = state.accessEmail;
}

function setupAccessGate() {
  const input = document.getElementById("accessEmail");
  const button = document.getElementById("accessSubmit");
  const status = document.getElementById("accessStatus");
  const changeButton = document.getElementById("changeEmailBtn");

  const submit = () => {
    const email = input.value.trim();
    if (!isValidEmail(email)) {
      status.textContent = TEXT.accessInvalid;
      return;
    }
    status.textContent = TEXT.accessStored;
    unlockAccess(email);
  };
  button?.addEventListener("click", submit);
  input?.addEventListener("keydown", event => {
    if (event.key === "Enter") submit();
  });

  changeButton?.addEventListener("click", () => {
    localStorage.removeItem(ACCESS_STORAGE_KEY);
    state.accessEmail = "";
    const overlay = document.getElementById("accessOverlay");
    const sessionEmail = document.getElementById("sessionEmail");
    if (sessionEmail) sessionEmail.textContent = "-";
    if (overlay) overlay.classList.remove("hidden");
    document.body.classList.add("access-locked");
    if (input) {
      input.value = "";
      input.focus();
    }
    if (status) status.textContent = "";
  });

  const storedEmail = localStorage.getItem(ACCESS_STORAGE_KEY) || "";
  if (isValidEmail(storedEmail)) {
    unlockAccess(storedEmail);
    return;
  }
  document.body.classList.add("access-locked");
}

const modelConfigs = {
  ns: { cols: "nsColumns", baseYear: "nsBaseYear", baseMonth: "nsBaseMonth", baseDay: "nsBaseDay", compareYear: "nsCompareYear", compareMonth: "nsCompareMonth", compareDay: "nsCompareDay", compare: "nsCompareDates", status: "nsStatus", curve: "nsCurveChart", factor: "nsFactorChart", betasDownload: "nsBetasDownload", curvesDownload: "nsCurvesDownload" },
  sv: { cols: "svColumns", baseYear: "svBaseYear", baseMonth: "svBaseMonth", baseDay: "svBaseDay", compareYear: "svCompareYear", compareMonth: "svCompareMonth", compareDay: "svCompareDay", compare: "svCompareDates", status: "svStatus", curve: "svCurveChart", factor: "svFactorChart", betasDownload: "svBetasDownload", curvesDownload: "svCurvesDownload" },
  sp: { cols: "spColumns", baseYear: "spBaseYear", baseMonth: "spBaseMonth", baseDay: "spBaseDay", compareYear: "spCompareYear", compareMonth: "spCompareMonth", compareDay: "spCompareDay", compare: "spCompareDates", status: "spStatus", curve: "spCurveChart", factor: "spObsChart", curvesDownload: "spCurvesDownload" },
};

function activatePanel(name) {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.panel === name));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.toggle("active", panel.id === `panel-${name}`));
  if (name === "nelson-siegel") runNelsonSiegel();
  if (name === "svensson") runSvensson();
  if (name === "cubic-spline") runSpline();
}

function parseCSV(text) {
  const [headerLine, ...lines] = text.trim().split(/\r?\n/);
  const headers = headerLine.split(",").map(value => value.trim());
  return lines.filter(Boolean).map(line => {
    const values = line.split(",").map(value => value.trim());
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return row;
  });
}

function normalizeRows(rawRows) {
  const parseRate = value => {
    if (value === null || value === undefined) return Number.NaN;
    const trimmed = String(value).trim();
    if (!trimmed) return Number.NaN;
    const normalized = trimmed.replace(/\s+/g, "");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  return rawRows.map(rawRow => {
    const row = {};
    Object.entries(rawRow).forEach(([key, value]) => {
      const mappedKey = LEGACY_ALIASES[key] || LEGACY_ALIASES[key.toLowerCase()] || key;
      row[mappedKey] = mappedKey === "Date" ? value : parseRate(value);
    });
    row.Date = rawRow.Date || rawRow.date;
    return row;
  }).filter(row => row.Date);
}

function availableColumns(rows) {
  if (!rows.length) return [];
  return Object.keys(rows[0])
    .filter(column => column !== "Date" && RATE_MONTHS[column])
    .sort((a, b) => RATE_MONTHS[a] - RATE_MONTHS[b]);
}

function availableDates(rows, columns) {
  return rows
    .filter(row => columns.every(column => Number.isFinite(row[column])))
    .map(row => row.Date)
    .sort();
}

function renderDataTable() {
  const head = document.getElementById("dataHead");
  const body = document.getElementById("dataBody");
  head.innerHTML = "";
  body.innerHTML = "";
  if (!state.rows.length) return;
  const baseColumns = availableColumns(state.rows);
  const rowsForTable = state.rows.map(row => {
    const dateText = String(row.Date || "");
    const [year = "", month = "", day = ""] = dateText.split("-");
    return {
      Date: dateText,
      Year: year,
      Month: month,
      Day: day,
      ...Object.fromEntries(baseColumns.map(column => [column, row[column]])),
    };
  });
  const columns = ["Date", "Year", "Month", "Day", ...baseColumns];
  const sortColumn = document.getElementById("dataSortColumn")?.value || "Date";
  const sortDirection = document.getElementById("dataSortDirection")?.value || "desc";
  const rowLimit = Number(document.getElementById("dataRowLimit")?.value || 10);
  const headRow = document.createElement("tr");
  columns.forEach(column => {
    const th = document.createElement("th");
    th.textContent = column;
    headRow.appendChild(th);
  });
  head.appendChild(headRow);
  const sortedRows = [...rowsForTable].sort((left, right) => {
    const a = left[sortColumn];
    const b = right[sortColumn];
    if (["Date", "Year", "Month", "Day"].includes(sortColumn)) {
      return sortDirection === "asc"
        ? String(a).localeCompare(String(b))
        : String(b).localeCompare(String(a));
    }
    const aNum = Number(a);
    const bNum = Number(b);
    return sortDirection === "asc" ? aNum - bNum : bNum - aNum;
  });
  sortedRows.slice(0, rowLimit).forEach(row => {
    const tr = document.createElement("tr");
    columns.forEach(column => {
      const td = document.createElement("td");
      td.textContent = typeof row[column] === "number" ? row[column].toFixed(4) : row[column];
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  document.getElementById("dataSummary").textContent = `${TEXT.loadedRows}: ${state.rows.length} | ${TEXT.series}: ${availableColumns(state.rows).join(", ")}`;
  setDownloadLink("dataDownload", sortedRows);
}

function setStatus(id, text) {
  document.getElementById(id).textContent = text;
}

function csvUrlFromRows(rows) {
  if (!rows?.length) return null;
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map(row => headers.map(header => row[header] ?? "").join(",")),
  ];
  return URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" }));
}

function setDownloadLink(id, rows) {
  const element = document.getElementById(id);
  const url = csvUrlFromRows(rows);
  if (url) {
    element.href = url;
    element.classList.remove("hidden-download");
  } else {
    element.href = "#";
    element.classList.add("hidden-download");
  }
}

function createColumnChips() {
  const columns = availableColumns(state.rows);
  Object.entries(modelConfigs).forEach(([key, config]) => {
    const container = document.getElementById(config.cols);
    container.innerHTML = "";
    columns.forEach(column => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `chip ${DEFAULT_COLUMNS.includes(column) ? "active" : ""}`.trim();
      chip.dataset.value = column;
      chip.textContent = column;
      chip.addEventListener("click", () => {
        chip.classList.toggle("active");
        if (key === "ns") runNelsonSiegel();
        if (key === "sv") runSvensson();
        if (key === "sp") runSpline();
      });
      container.appendChild(chip);
    });
  });
}

function selectedColumns(key) {
  return [...document.querySelectorAll(`#${modelConfigs[key].cols} .chip.active`)].map(chip => chip.dataset.value);
}

function unique(values) {
  return [...new Set(values)];
}

function buildDateMap(dates) {
  const years = unique(dates.map(date => date.slice(0, 4)));
  const monthsByYear = {};
  const daysByYearMonth = {};
  years.forEach(year => {
    const yearDates = dates.filter(date => date.startsWith(`${year}-`));
    monthsByYear[year] = unique(yearDates.map(date => date.slice(5, 7)));
    monthsByYear[year].forEach(month => {
      const key = `${year}-${month}`;
      daysByYearMonth[key] = unique(yearDates.filter(date => date.startsWith(`${key}-`)).map(date => date.slice(8, 10)));
    });
  });
  return { years, monthsByYear, daysByYearMonth };
}

function fillSelect(select, values, placeholder, selectedValue = "") {
  select.innerHTML = "";
  const placeholderOption = document.createElement("option");
  placeholderOption.value = "";
  placeholderOption.textContent = placeholder;
  placeholderOption.selected = !selectedValue;
  select.appendChild(placeholderOption);
  values.forEach(value => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = value === selectedValue;
    select.appendChild(option);
  });
}

function currentBaseDate(key) {
  const config = modelConfigs[key];
  const year = document.getElementById(config.baseYear).value;
  const month = document.getElementById(config.baseMonth).value;
  const day = document.getElementById(config.baseDay).value;
  return year && month && day ? `${year}-${month}-${day}` : "";
}

function setBaseDate(key, date, triggerPlot = false) {
  const config = modelConfigs[key];
  const dates = state.availableDates[key] || [];
  if (!dates.includes(date)) return;
  const map = buildDateMap(dates);
  const [year, month, day] = date.split("-");
  const yearSelect = document.getElementById(config.baseYear);
  const monthSelect = document.getElementById(config.baseMonth);
  const daySelect = document.getElementById(config.baseDay);
  fillSelect(yearSelect, map.years, LANG === "en" ? "Year" : "Año", year);
  fillSelect(monthSelect, map.monthsByYear[year] || [], LANG === "en" ? "Month" : "Mes", month);
  fillSelect(daySelect, map.daysByYearMonth[`${year}-${month}`] || [], LANG === "en" ? "Day" : "Día", day);
  if (triggerPlot && state.calculations[key]) plotModel(key);
}

function wireBaseDateControls(key) {
  const config = modelConfigs[key];
  const yearSelect = document.getElementById(config.baseYear);
  const monthSelect = document.getElementById(config.baseMonth);
  const daySelect = document.getElementById(config.baseDay);
  const map = buildDateMap(state.availableDates[key] || []);

  yearSelect.onchange = () => {
    const year = yearSelect.value;
    fillSelect(monthSelect, year ? (map.monthsByYear[year] || []) : [], LANG === "en" ? "Month" : "Mes");
    fillSelect(daySelect, [], LANG === "en" ? "Day" : "Día");
  };
  monthSelect.onchange = () => {
    const year = yearSelect.value;
    const month = monthSelect.value;
    fillSelect(daySelect, year && month ? (map.daysByYearMonth[`${year}-${month}`] || []) : [], LANG === "en" ? "Day" : "Día");
  };
  daySelect.onchange = () => {
    if (state.calculations[key]) plotModel(key);
  };
}

function wireCompareDateControls(key) {
  const config = modelConfigs[key];
  const yearSelect = document.getElementById(config.compareYear);
  const monthSelect = document.getElementById(config.compareMonth);
  const daySelect = document.getElementById(config.compareDay);
  const map = buildDateMap(state.availableDates[key] || []);

  fillSelect(yearSelect, map.years, LANG === "en" ? "Year" : "Año");
  fillSelect(monthSelect, [], LANG === "en" ? "Month" : "Mes");
  fillSelect(daySelect, [], LANG === "en" ? "Day" : "Día");

  yearSelect.onchange = () => {
    const year = yearSelect.value;
    fillSelect(monthSelect, year ? (map.monthsByYear[year] || []) : [], LANG === "en" ? "Month" : "Mes");
    fillSelect(daySelect, [], LANG === "en" ? "Day" : "Día");
  };
  monthSelect.onchange = () => {
    const year = yearSelect.value;
    const month = monthSelect.value;
    fillSelect(daySelect, year && month ? (map.daysByYearMonth[`${year}-${month}`] || []) : [], LANG === "en" ? "Day" : "Día");
  };
  daySelect.onchange = () => {
    const year = yearSelect.value;
    const month = monthSelect.value;
    const day = daySelect.value;
    if (year && month && day) {
      addCompareChip(key, `${year}-${month}-${day}`);
      fillSelect(yearSelect, map.years, LANG === "en" ? "Year" : "Año");
      fillSelect(monthSelect, [], LANG === "en" ? "Month" : "Mes");
      fillSelect(daySelect, [], LANG === "en" ? "Day" : "Día");
    }
  };
}

function shiftDateString(date, offset) {
  const raw = new Date(`${date}T00:00:00`);
  const shifted = new Date(raw);
  if (offset === "1m") shifted.setMonth(shifted.getMonth() - 1);
  if (offset === "3m") shifted.setMonth(shifted.getMonth() - 3);
  if (offset === "1y") shifted.setFullYear(shifted.getFullYear() - 1);
  return shifted.toISOString().slice(0, 10);
}

function nearestAvailableDate(key, targetDate) {
  const dates = state.availableDates[key] || [];
  const target = new Date(`${targetDate}T00:00:00`).getTime();
  const eligible = dates.filter(date => new Date(`${date}T00:00:00`).getTime() <= target);
  return eligible.length ? eligible[eligible.length - 1] : "";
}

function fillDateControls(key, dates) {
  state.availableDates[key] = dates;
  const compareContainer = document.getElementById(modelConfigs[key].compare);
  compareContainer.innerHTML = "";
  const latest = dates[dates.length - 1] || "";
  setBaseDate(key, latest, false);
  wireBaseDateControls(key);
  wireCompareDateControls(key);
}

function initializeAllDateControls(rows) {
  const allColumns = availableColumns(rows);
  Object.keys(modelConfigs).forEach(key => {
    const fallbackColumns = key === "sp" ? DEFAULT_COLUMNS : DEFAULT_COLUMNS;
    const usableColumns = fallbackColumns.filter(column => allColumns.includes(column));
    const dates = availableDates(rows, usableColumns);
    fillDateControls(key, dates);
  });
}

function addCompareChip(key, date) {
  const container = document.getElementById(modelConfigs[key].compare);
  if ([...container.querySelectorAll(".chip")].some(chip => chip.dataset.value === date)) return;
  if (container.querySelectorAll(".chip").length >= 5) return;
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip active";
  chip.dataset.value = date;
  chip.textContent = `${date} ×`;
  chip.addEventListener("click", () => {
    chip.remove();
    if (state.calculations[key]) plotModel(key);
  });
  container.appendChild(chip);
  [...container.querySelectorAll(".chip")]
    .sort((a, b) => a.dataset.value.localeCompare(b.dataset.value))
    .forEach(node => container.appendChild(node));
  if (state.calculations[key]) plotModel(key);
}

function plotLayout(xTitle, yTitle) {
  const isMaturityAxis = xTitle.toLowerCase().includes("madurez") || xTitle.toLowerCase().includes("maturity");
  return {
    paper_bgcolor: "#0b1016",
    plot_bgcolor: "#0f1822",
    margin: { l: 54, r: 20, t: 18, b: 52 },
    font: { color: "#dde7f1", family: "Space Grotesk, sans-serif" },
    legend: { orientation: "h", x: 0, y: 1.08, bgcolor: "rgba(0,0,0,0)" },
    xaxis: { title: xTitle, range: isMaturityAxis ? [-5, 125] : undefined, gridcolor: "#223548", zerolinecolor: "#223548" },
    yaxis: { title: yTitle, gridcolor: "#223548", zerolinecolor: "#223548" },
  };
}

function curveTraces(curves) {
  const palette = [
    { line: "#ffb000", point: "#ffd166" },
    { line: "#35c2ff", point: "#7ae582" },
    { line: "#ff6b6b", point: "#c7f464" },
    { line: "#c792ea", point: "#82aaff" },
  ];
  const traces = [];
  curves.forEach((curve, idx) => {
    const colors = palette[idx % palette.length];
    traces.push({ x: curve.curveMonths, y: curve.estimated, type: "scatter", mode: "lines", name: `${TEXT.estimatedPrefix} ${curve.date}`, line: { color: colors.line, width: 3 } });
    traces.push({ x: curve.observedMonths, y: curve.observed, type: "scatter", mode: "lines+markers", name: `${TEXT.observedPrefix} ${curve.date}`, line: { color: colors.point, width: 1.5, dash: "dot" }, marker: { color: colors.point, size: 9, line: { color: "#081018", width: 1 } } });
  });
  return traces;
}

function factorTraces(factors) {
  const colors = ["#ffb000", "#35c2ff", "#ffd166", "#7ae582"];
  return factors.map((factor, index) => ({ x: factor.dates, y: factor.values, type: "scatter", mode: "lines", name: factor.name, line: { color: colors[index % colors.length], width: 2 } }));
}

function runNelsonSiegel() {
  if (!state.rows.length) return;
  const columns = selectedColumns("ns");
  if (columns.length < 3) {
    setStatus("nsStatus", TEXT.selectAtLeast3);
    return;
  }
  const lambdaValue = Number(document.getElementById("nsLambda").value);
  const result = fitNelsonSiegel(state.rows, columns, lambdaValue);
  const dates = availableDates(result.observed, result.columns);
  if (!dates.length) {
    setStatus("nsStatus", TEXT.noCompleteDates);
    return;
  }
  state.calculations.ns = { ...result, lambdaValue, dates };
  fillDateControls("ns", dates);
  plotModel("ns");
}

function runSvensson() {
  if (!state.rows.length) return;
  const columns = selectedColumns("sv");
  if (columns.length < 4) {
    setStatus("svStatus", TEXT.selectAtLeast4);
    return;
  }
  const lambda1 = Number(document.getElementById("svLambda1").value);
  const lambda2 = Number(document.getElementById("svLambda2").value);
  const result = fitSvensson(state.rows, columns, lambda1, lambda2);
  const dates = availableDates(result.observed, result.columns);
  if (!dates.length) {
    setStatus("svStatus", TEXT.noCompleteDates);
    return;
  }
  state.calculations.sv = { ...result, lambda1, lambda2, dates };
  fillDateControls("sv", dates);
  plotModel("sv");
}

function runSpline() {
  if (!state.rows.length) return;
  const columns = selectedColumns("sp");
  if (columns.length < 3) {
    setStatus("spStatus", TEXT.selectAtLeast3);
    return;
  }
  const observed = state.rows.filter(row => columns.every(column => Number.isFinite(row[column])));
  const dates = availableDates(observed, columns);
  if (!dates.length) {
    setStatus("spStatus", TEXT.noCompleteDates);
    return;
  }
  state.calculations.sp = { observed, columns, dates };
  fillDateControls("sp", dates);
  plotModel("sp");
}

function buildCurveSelection(key) {
  const baseDate = currentBaseDate(key);
  const compareDates = [...document.querySelectorAll(`#${modelConfigs[key].compare} .chip.active`)].map(chip => chip.dataset.value);
  return [baseDate, ...compareDates.filter(date => date && date !== baseDate)].filter(Boolean).slice(0, 6);
}

function plotModel(key) {
  if (!state.calculations[key]) return;
  if (key === "ns") {
    const calc = state.calculations.ns;
    const curveDates = buildCurveSelection("ns");
    if (!curveDates.length) return;
    const months = Array.from({ length: 120 }, (_, i) => i + 1);
    const curves = curveDates.map(date => {
      const row = calc.observed.find(item => item.Date === date);
      const beta = calc.betas.find(item => item.Date === date);
      return {
        date,
        curveMonths: months,
        estimated: reconstructNelsonSiegelCurve(months, beta, calc.lambdaValue),
        observedMonths: calc.columns.map(column => RATE_MONTHS[column]),
        observed: calc.columns.map(column => row[column]),
      };
    });
    const factors = [
      { name: "level", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.level) },
      { name: "slope", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.slope) },
      { name: "curvature", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.curvature) },
    ];
    Plotly.newPlot("nsCurveChart", curveTraces(curves), plotLayout(TEXT.maturityMonths, TEXT.rate), { responsive: true, displayModeBar: false });
    Plotly.newPlot("nsFactorChart", factorTraces(factors), plotLayout(TEXT.date, TEXT.factor), { responsive: true, displayModeBar: false });
    setDownloadLink("nsBetasDownload", calc.betas);
    const curveRows = [];
    curves.forEach(curve => {
      curve.curveMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, EstimatedRate: curve.estimated[index] }));
      curve.observedMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, ObservedRate: curve.observed[index] }));
    });
    setDownloadLink("nsCurvesDownload", curveRows);
    setStatus("nsStatus", TEXT.chartUpdated);
  }
  if (key === "sv") {
    const calc = state.calculations.sv;
    const curveDates = buildCurveSelection("sv");
    if (!curveDates.length) return;
    const months = Array.from({ length: 120 }, (_, i) => i + 1);
    const curves = curveDates.map(date => {
      const row = calc.observed.find(item => item.Date === date);
      const beta = calc.betas.find(item => item.Date === date);
      return {
        date,
        curveMonths: months,
        estimated: reconstructSvenssonCurve(months, beta, calc.lambda1, calc.lambda2),
        observedMonths: calc.columns.map(column => RATE_MONTHS[column]),
        observed: calc.columns.map(column => row[column]),
      };
    });
    const factors = [
      { name: "level", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.level) },
      { name: "slope", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.slope) },
      { name: "curv_1", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.curvature_1) },
      { name: "curv_2", dates: calc.betas.map(beta => beta.Date), values: calc.betas.map(beta => beta.curvature_2) },
    ];
    Plotly.newPlot("svCurveChart", curveTraces(curves), plotLayout(TEXT.maturityMonths, TEXT.rate), { responsive: true, displayModeBar: false });
    Plotly.newPlot("svFactorChart", factorTraces(factors), plotLayout(TEXT.date, TEXT.factor), { responsive: true, displayModeBar: false });
    setDownloadLink("svBetasDownload", calc.betas);
    const curveRows = [];
    curves.forEach(curve => {
      curve.curveMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, EstimatedRate: curve.estimated[index] }));
      curve.observedMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, ObservedRate: curve.observed[index] }));
    });
    setDownloadLink("svCurvesDownload", curveRows);
    setStatus("svStatus", TEXT.chartUpdated);
  }
  if (key === "sp") {
    const calc = state.calculations.sp;
    const curveDates = buildCurveSelection("sp");
    if (!curveDates.length) return;
    const months = Array.from({ length: RATE_MONTHS[calc.columns[0]] }, (_, i) => i + 1);
    const curves = curveDates.map(date => {
      const row = calc.observed.find(item => item.Date === date);
      const observedMonths = calc.columns.map(column => RATE_MONTHS[column]);
      const observed = calc.columns.map(column => row[column]);
      const curveMonths = Array.from({ length: observedMonths[observedMonths.length - 1] }, (_, i) => i + 1);
      return {
        date,
        curveMonths,
        estimated: naturalCubicSpline(observedMonths, observed, curveMonths),
        observedMonths,
        observed,
      };
    });
    Plotly.newPlot("spCurveChart", curveTraces(curves), plotLayout(TEXT.maturityMonths, TEXT.rate), { responsive: true, displayModeBar: false });
    const obsTraces = curves.map(curve => ({
      x: curve.observedMonths,
      y: curve.observed,
      type: "scatter",
      mode: "lines+markers",
      name: `${TEXT.observedPrefix} ${curve.date}`,
      line: { color: "#ffd166", width: 1.5, dash: "dot" },
      marker: { color: "#ffd166", size: 9, line: { color: "#081018", width: 1 } },
    }));
    Plotly.newPlot("spObsChart", obsTraces, plotLayout(TEXT.maturityMonths, TEXT.observedRate), { responsive: true, displayModeBar: false });
    const curveRows = [];
    curves.forEach(curve => {
      curve.curveMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, EstimatedRate: curve.estimated[index] }));
      curve.observedMonths.forEach((month, index) => curveRows.push({ Date: curve.date, MaturityMonths: month, ObservedRate: curve.observed[index] }));
    });
    setDownloadLink("spCurvesDownload", curveRows);
    setStatus("spStatus", TEXT.chartUpdated);
  }
}

function setRows(rows) {
  state.rows = rows;
  const columns = ["Date", "Year", "Month", "Day", ...availableColumns(rows)];
  const sortSelect = document.getElementById("dataSortColumn");
  sortSelect.innerHTML = "";
  columns.forEach(column => {
    const option = document.createElement("option");
    option.value = column;
    option.textContent = column;
    sortSelect.appendChild(option);
  });
  sortSelect.value = "Date";
  renderDataTable();
  createColumnChips();
  initializeAllDateControls(rows);
  const completeDefaultDates = availableDates(rows, DEFAULT_COLUMNS);
  const firstDate = rows[0]?.Date || "-";
  const lastDate = rows[rows.length - 1]?.Date || "-";
  setGlobalStatus(TEXT.loadedBase(rows.length, firstDate, lastDate, completeDefaultDates.length));
}

function loadEmbeddedMarketData() {
  try {
    const rows = normalizeRows(MARKET_ROWS);
    if (!rows.length) {
      throw new Error(TEXT.emptyBase);
    }
    setRows(rows);
  } catch (error) {
    setGlobalStatus(error.message || TEXT.failedLoad);
  }
}

window.addEventListener("error", event => {
  setGlobalStatus(`Error JS: ${event.message}`);
});

window.addEventListener("unhandledrejection", event => {
  const message = event.reason?.message || String(event.reason || "Error async");
  setGlobalStatus(`Error JS: ${message}`);
});

try {
  setupAccessGate();
  document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => activatePanel(tab.dataset.panel)));
  document.querySelectorAll(".preset-btn").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.model;
      const baseDate = currentBaseDate(key);
      if (!baseDate) return;
      const shifted = shiftDateString(baseDate, button.dataset.offset);
      const nearest = nearestAvailableDate(key, shifted);
      if (nearest) addCompareChip(key, nearest);
    });
  });
  document.getElementById("nsLambda")?.addEventListener("change", runNelsonSiegel);
  document.getElementById("svLambda1")?.addEventListener("change", runSvensson);
  document.getElementById("svLambda2")?.addEventListener("change", runSvensson);
  document.getElementById("dataSortColumn").addEventListener("change", renderDataTable);
  document.getElementById("dataSortDirection").addEventListener("change", renderDataTable);
  document.getElementById("dataRowLimit").addEventListener("change", renderDataTable);
  loadEmbeddedMarketData();
} catch (error) {
  setGlobalStatus(`Error JS: ${error.message || error}`);
}
