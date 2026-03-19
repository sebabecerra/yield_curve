export const RATE_MONTHS = {
  TPM: 1,
  SPC_03Y: 3,
  SPC_06Y: 6,
  SPC_1Y: 12,
  SPC_2Y: 24,
  SPC_3Y: 36,
  SPC_4Y: 48,
  SPC_5Y: 60,
  SPC_10Y: 120,
};

export const LEGACY_ALIASES = {
  tpm: "TPM",
  scp90: "SPC_03Y",
  scp180: "SPC_06Y",
  scp360: "SPC_1Y",
  spc_pesos_2y: "SPC_2Y",
  spc_pesos_3y: "SPC_3Y",
  spc_pesos_4y: "SPC_4Y",
  spc_pesos_5y: "SPC_5Y",
  spc_pesos_10y: "SPC_10Y",
};

function transpose(matrix) {
  return matrix[0].map((_, colIndex) => matrix.map(row => row[colIndex]));
}

function multiply(a, b) {
  return a.map(row => b[0].map((_, j) => row.reduce((sum, value, i) => sum + value * b[i][j], 0)));
}

function multiplyMatrixVector(matrix, vector) {
  return matrix.map(row => row.reduce((sum, value, index) => sum + value * vector[index], 0));
}

function solveLinearSystem(matrix, vector) {
  const n = matrix.length;
  const augmented = matrix.map((row, i) => [...row, vector[i]]);
  for (let i = 0; i < n; i += 1) {
    let maxRow = i;
    for (let j = i + 1; j < n; j += 1) {
      if (Math.abs(augmented[j][i]) > Math.abs(augmented[maxRow][i])) maxRow = j;
    }
    [augmented[i], augmented[maxRow]] = [augmented[maxRow], augmented[i]];
    const pivot = augmented[i][i];
    if (Math.abs(pivot) < 1e-12) throw new Error("La matriz es singular o casi singular.");
    for (let j = i; j <= n; j += 1) augmented[i][j] /= pivot;
    for (let k = 0; k < n; k += 1) {
      if (k === i) continue;
      const factor = augmented[k][i];
      for (let j = i; j <= n; j += 1) augmented[k][j] -= factor * augmented[i][j];
    }
  }
  return augmented.map(row => row[n]);
}

export function leastSquares(design, y) {
  const xt = transpose(design);
  const xtx = multiply(xt, design);
  const xty = multiplyMatrixVector(xt, y);
  return solveLinearSystem(xtx, xty);
}

export function nelsonSiegelLoadings(tauYears, lambdaValue) {
  return tauYears.map(tau => {
    const level = 1;
    const slope = (1 - Math.exp(-lambdaValue * tau)) / (lambdaValue * tau);
    const curvature = slope - Math.exp(-lambdaValue * tau);
    return [level, slope, curvature];
  });
}

export function svenssonLoadings(tauYears, lambda1, lambda2) {
  return tauYears.map(tau => {
    const level = 1;
    const slope = (1 - Math.exp(-lambda1 * tau)) / (lambda1 * tau);
    const curvature1 = slope - Math.exp(-lambda1 * tau);
    const curvature2 = ((1 - Math.exp(-lambda2 * tau)) / (lambda2 * tau)) - Math.exp(-lambda2 * tau);
    return [level, slope, curvature1, curvature2];
  });
}

function evaluateDesign(design, betas) {
  return design.map(row => row.reduce((sum, value, index) => sum + value * betas[index], 0));
}

export function fitNelsonSiegel(rows, columns, lambdaValue) {
  const sortedColumns = [...columns].sort((a, b) => RATE_MONTHS[a] - RATE_MONTHS[b]);
  const observed = rows.filter(row => sortedColumns.every(column => Number.isFinite(row[column])));
  const tauYears = sortedColumns.map(column => RATE_MONTHS[column] / 12);
  const design = nelsonSiegelLoadings(tauYears, lambdaValue);
  const betas = observed.map(row => {
    const y = sortedColumns.map(column => row[column]);
    const beta = leastSquares(design, y);
    return { Date: row.Date, level: beta[0], slope: beta[1], curvature: beta[2] };
  });
  return { observed, betas, columns: sortedColumns };
}

export function fitSvensson(rows, columns, lambda1, lambda2) {
  const sortedColumns = [...columns].sort((a, b) => RATE_MONTHS[a] - RATE_MONTHS[b]);
  const observed = rows.filter(row => sortedColumns.every(column => Number.isFinite(row[column])));
  const tauYears = sortedColumns.map(column => RATE_MONTHS[column] / 12);
  const design = svenssonLoadings(tauYears, lambda1, lambda2);
  const betas = observed.map(row => {
    const y = sortedColumns.map(column => row[column]);
    const beta = leastSquares(design, y);
    return { Date: row.Date, level: beta[0], slope: beta[1], curvature_1: beta[2], curvature_2: beta[3] };
  });
  return { observed, betas, columns: sortedColumns };
}

export function reconstructNelsonSiegelCurve(months, betasRow, lambdaValue) {
  const tauYears = months.map(month => month / 12);
  const design = nelsonSiegelLoadings(tauYears, lambdaValue);
  return evaluateDesign(design, [betasRow.level, betasRow.slope, betasRow.curvature]);
}

export function reconstructSvenssonCurve(months, betasRow, lambda1, lambda2) {
  const tauYears = months.map(month => month / 12);
  const design = svenssonLoadings(tauYears, lambda1, lambda2);
  return evaluateDesign(design, [betasRow.level, betasRow.slope, betasRow.curvature_1, betasRow.curvature_2]);
}

export function fitAr1Series(values) {
  const cleaned = values.filter(value => Number.isFinite(value));
  if (cleaned.length < 2) throw new Error("Se necesitan al menos 2 observaciones para AR(1).");
  const x = cleaned.slice(0, -1);
  const y = cleaned.slice(1);
  const xMean = x.reduce((sum, value) => sum + value, 0) / x.length;
  const yMean = y.reduce((sum, value) => sum + value, 0) / y.length;
  const numerator = x.reduce((sum, value, index) => sum + ((value - xMean) * (y[index] - yMean)), 0);
  const denominator = x.reduce((sum, value) => sum + ((value - xMean) ** 2), 0);
  const phi = Math.abs(denominator) < 1e-12 ? 0 : numerator / denominator;
  const intercept = yMean - (phi * xMean);
  const residuals = y.map((value, index) => value - intercept - (phi * x[index]));
  const sigma = Math.sqrt(residuals.reduce((sum, value) => sum + (value ** 2), 0) / residuals.length);
  return { intercept, phi, sigma };
}

export function projectAr1Series(model, lastValue, horizonSteps) {
  const projected = [];
  let current = lastValue;
  for (let step = 1; step <= horizonSteps; step += 1) {
    current = model.intercept + (model.phi * current);
    projected.push(current);
  }
  return projected;
}

export function naturalCubicSpline(x, y, xTarget) {
  const n = x.length;
  if (n < 3) throw new Error("Se necesitan al menos 3 puntos para spline.");
  const a = [...y];
  const h = Array.from({ length: n - 1 }, (_, i) => x[i + 1] - x[i]);
  const alpha = Array(n).fill(0);
  for (let i = 1; i < n - 1; i += 1) {
    alpha[i] = (3 / h[i]) * (a[i + 1] - a[i]) - (3 / h[i - 1]) * (a[i] - a[i - 1]);
  }
  const l = Array(n).fill(0);
  const mu = Array(n).fill(0);
  const z = Array(n).fill(0);
  const c = Array(n).fill(0);
  const b = Array(n - 1).fill(0);
  const d = Array(n - 1).fill(0);
  l[0] = 1;
  for (let i = 1; i < n - 1; i += 1) {
    l[i] = 2 * (x[i + 1] - x[i - 1]) - h[i - 1] * mu[i - 1];
    mu[i] = h[i] / l[i];
    z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i];
  }
  l[n - 1] = 1;
  for (let j = n - 2; j >= 0; j -= 1) {
    c[j] = z[j] - mu[j] * c[j + 1];
    b[j] = ((a[j + 1] - a[j]) / h[j]) - (h[j] * (c[j + 1] + 2 * c[j])) / 3;
    d[j] = (c[j + 1] - c[j]) / (3 * h[j]);
  }
  return xTarget.map(value => {
    let i = n - 2;
    for (let j = 0; j < n - 1; j += 1) {
      if (value >= x[j] && value <= x[j + 1]) {
        i = j;
        break;
      }
    }
    const diff = value - x[i];
    return a[i] + b[i] * diff + c[i] * diff ** 2 + d[i] * diff ** 3;
  });
}
