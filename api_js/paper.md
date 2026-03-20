# L3 | Yield Curve Analytics

## Resumen

Este documento resume la metodología implementada en la aplicación web estática de analítica de curva de tasas. La plataforma estima, compara y visualiza estructuras temporales de tasas de interés directamente en el navegador, usando una base de mercado ya incorporada en el sitio.

La aplicación combina cuatro bloques analíticos:

1. ajuste `Nelson-Siegel`;
2. ajuste `Nelson-Siegel-Svensson`;
3. interpolación `Cubic spline`;
4. módulos dinámicos basados en `AR(1)` y `Kalman`.

La motivación es convertir una lógica cuantitativa normalmente encapsulada en notebooks en una experiencia web usable, visual y publicable como sitio estático.

---

## 1. Objetivo

La plataforma busca resolver cuatro necesidades:

1. transformar tasas observadas en curvas continuas comparables por fecha;
2. mostrar curvas spot y curvas forward de forma inmediata;
3. permitir comparación histórica entre fechas de mercado;
4. ofrecer una capa simple de proyección y una versión dinámica suavizada de factores.

---

## 2. Universo de datos

La base incorporada trabaja con los siguientes nodos:

- `TPM`
- `SPC_03Y`
- `SPC_06Y`
- `SPC_1Y`
- `SPC_2Y`
- `SPC_3Y`
- `SPC_4Y`
- `SPC_5Y`
- `SPC_10Y`

Madureces en meses:

$$
\mathcal{M} = \{1, 3, 6, 12, 24, 36, 48, 60, 120\}
$$

La aplicación opera con un dataset ya embebido, por lo que no requiere carga manual de archivos ni backend.

---

## 3. Limpieza y normalización

Antes de estimar, la aplicación:

- normaliza aliases legacy;
- convierte `Date` a índice temporal usable;
- convierte columnas de tasas a numérico;
- conserva vacíos reales como `NaN`;
- filtra solo fechas completas para las series seleccionadas.

Ejemplo de normalización:

$$
\texttt{spc\_pesos\_2y} \rightarrow \texttt{SPC\_2Y}
$$

Conversión de tipos:

$$
x_{t,m} =
\begin{cases}
\mathrm{float}(v), & \text{si } v \text{ es parseable} \\
\mathrm{NaN}, & \text{si } v \text{ es vacío o inválido}
\end{cases}
$$

Una fecha `t` es usable para un conjunto de columnas `C` si:

$$
\forall c \in C,\quad x_{t,c} \in \mathbb{R}
$$

---

## 4. Notación

- `tau`: madurez en años
- `m`: madurez en meses
- `y_t(tau)`: tasa spot observada o estimada en la fecha `t`
- `beta_t`: vector de factores del modelo
- `lambda`: parámetro de decaimiento
- `epsilon_t`: error de medición
- `eta_t`: ruido de transición

Relación meses-años:

$$
\tau = \frac{m}{12}
$$

---

## 5. Modelo Nelson-Siegel

La curva se modela como:

$$
y_t(\tau)=
\beta_{1,t}
+
\beta_{2,t}\left(\frac{1-e^{-\lambda\tau}}{\lambda\tau}\right)
+
\beta_{3,t}\left(\frac{1-e^{-\lambda\tau}}{\lambda\tau} - e^{-\lambda\tau}\right)
$$

Interpretación de factores:

- `beta_1,t`: nivel
- `beta_2,t`: pendiente
- `beta_3,t`: curvatura

Definiciones:

$$
L(\tau,\lambda)=\frac{1-e^{-\lambda\tau}}{\lambda\tau}
$$

$$
C(\tau,\lambda)=L(\tau,\lambda)-e^{-\lambda\tau}
$$

Entonces:

$$
y_t(\tau)=\beta_{1,t}+\beta_{2,t}L(\tau,\lambda)+\beta_{3,t}C(\tau,\lambda)
$$

La estimación por fecha se realiza por mínimos cuadrados:

$$
\hat{\beta}_t=(X_t'X_t)^{-1}X_t'y_t
$$

donde:

$$
X_t=
\begin{bmatrix}
1 & L(\tau_1,\lambda) & C(\tau_1,\lambda) \\
1 & L(\tau_2,\lambda) & C(\tau_2,\lambda) \\
\vdots & \vdots & \vdots \\
1 & L(\tau_n,\lambda) & C(\tau_n,\lambda)
\end{bmatrix}
$$

---

## 6. Modelo Nelson-Siegel-Svensson

La extensión Svensson agrega una segunda curvatura:

$$
y_t(\tau)=
\beta_{1,t}
+
\beta_{2,t}L(\tau,\lambda_1)
+
\beta_{3,t}C_1(\tau,\lambda_1)
+
\beta_{4,t}C_2(\tau,\lambda_2)
$$

Definiciones:

$$
C_1(\tau,\lambda_1)=\frac{1-e^{-\lambda_1\tau}}{\lambda_1\tau}-e^{-\lambda_1\tau}
$$

$$
C_2(\tau,\lambda_2)=\frac{1-e^{-\lambda_2\tau}}{\lambda_2\tau}-e^{-\lambda_2\tau}
$$

Se estima de manera análoga:

$$
\hat{\beta}_t=(X_t'X_t)^{-1}X_t'y_t
$$

pero con cuatro columnas en la matriz de diseño.

---

## 7. Cubic spline natural

El spline cúbico natural interpola los nodos observados mediante polinomios por tramo:

$$
s_i(\tau)=a_i+b_i(\tau-\tau_i)+c_i(\tau-\tau_i)^2+d_i(\tau-\tau_i)^3
$$

Sujeto a:

- continuidad en nivel;
- continuidad en primera derivada;
- continuidad en segunda derivada;
- condiciones naturales en extremos:

$$
s''(\tau_1)=0,\qquad s''(\tau_n)=0
$$

Este enfoque es útil cuando se prefiere suavidad sobre interpretación económica de factores.

---

## 8. Curvas forward

La aplicación deriva forwards discretas entre meses consecutivos a partir de la curva spot:

$$
f(t_1,t_2)=
\left(
\frac{(1+z(t_2))^{t_2}}{(1+z(t_1))^{t_1}}
\right)^{\frac{1}{t_2-t_1}} - 1
$$

En la implementación:

$$
t_2 = t_1 + \frac{1}{12}
$$

Esto produce una curva forward mensual implícita por la curva spot estimada.

---

## 9. Proyección AR(1) sobre factores

Para cada factor de Nelson-Siegel se ajusta un proceso independiente:

$$
x_t = a + \phi x_{t-1} + \varepsilon_t
$$

con:

$$
\varepsilon_t \sim (0,\sigma^2)
$$

La proyección recursiva a `h` pasos es:

$$
\hat{x}_{T+1}=a+\phi x_T
$$

$$
\hat{x}_{T+2}=a+\phi \hat{x}_{T+1}
$$

$$
\hat{x}_{T+h}=a+\phi \hat{x}_{T+h-1}
$$

Los betas proyectados se usan para reconstruir la curva futura:

$$
\hat{y}_{T+h}(\tau)=
\hat{\beta}_{1,T+h}
+
\hat{\beta}_{2,T+h}L(\tau,\lambda)
+
\hat{\beta}_{3,T+h}C(\tau,\lambda)
$$

Esta pestaña entrega:

- curva actual estimada;
- curva observada;
- curvas proyectadas por horizonte;
- curvas forward correspondientes.

---

## 10. Dynamic Nelson-Siegel con Kalman

La pestaña `Kalman` usa una formulación de espacio de estados donde la estructura Nelson-Siegel actúa como ecuación de medición y los factores evolucionan con persistencia propia.

### 10.1 Ecuación de medición

$$
y_t = H(\lambda)\alpha_t + \varepsilon_t
$$

donde:

- `y_t`: vector de tasas observadas
- `alpha_t = [beta_1,t, beta_2,t, beta_3,t]'`: estado latente
- `H(lambda)`: matriz de cargas Nelson-Siegel
- `epsilon_t ~ N(0, R)`: error de medición

### 10.2 Ecuación de transición

$$
\alpha_t = c + F\alpha_{t-1} + \eta_t
$$

con transición diagonal:

$$
F =
\begin{bmatrix}
\phi_1 & 0 & 0 \\
0 & \phi_2 & 0 \\
0 & 0 & \phi_3
\end{bmatrix}
$$

y:

$$
\eta_t \sim \mathcal{N}(0,Q)
$$

### 10.3 Calibración aproximada

La implementación actual usa una aproximación parsimoniosa:

1. estima Nelson-Siegel estático fecha a fecha;
2. ajusta un `AR(1)` separado sobre `level`, `slope` y `curvature`;
3. usa las varianzas residuales para construir `Q`;
4. usa residuos cross-sectional para aproximar `R`.

### 10.4 Filtro

Predicción:

$$
a_{t|t-1}=c+Fa_{t-1|t-1}
$$

$$
P_{t|t-1}=FP_{t-1|t-1}F'+Q
$$

Innovación:

$$
v_t=y_t-Ha_{t|t-1}
$$

$$
S_t=HP_{t|t-1}H'+R
$$

Ganancia:

$$
K_t=P_{t|t-1}H'S_t^{-1}
$$

Actualización:

$$
a_{t|t}=a_{t|t-1}+K_tv_t
$$

$$
P_{t|t}=(I-K_tH)P_{t|t-1}
$$

### 10.5 Suavizado

La app además aplica un backward smoother:

$$
J_t=P_{t|t}F'P_{t+1|t}^{-1}
$$

$$
a_{t|T}=a_{t|t}+J_t(a_{t+1|T}-a_{t+1|t})
$$

### 10.6 Resultado

La salida visible para el usuario es:

- curva spot filtrada;
- curva forward filtrada;
- comparación entre fechas bajo una trayectoria latente suavizada.

Esta implementación no pretende ser una estimación institucional completa de `Dynamic Nelson-Siegel`, sino una aproximación parsimoniosa y usable en frontend.

---

## 11. Descargas

La aplicación permite descargar:

- datos limpios;
- curvas spot;
- curvas forward;
- proyecciones por horizonte.

Cada descarga se genera localmente en el navegador mediante `Blob` y un enlace temporal.

---

## 12. Limitaciones

- la base es embebida y no se actualiza automáticamente;
- no hay backend ni persistencia de usuario;
- la proyección `AR(1)` es deliberadamente simple;
- el módulo `Kalman` es una versión reducida y exploratoria, no una calibración full maximum-likelihood.

---

## 13. Conclusión

La herramienta se posiciona como un puente entre:

- analítica cuantitativa;
- visualización ejecutiva;
- simplicidad de despliegue;
- prototipado serio de herramientas de renta fija.

No busca reemplazar una plataforma institucional completa, sino convertir una base real de tasas y modelos estándar de curva en una experiencia web legible, usable y publicable.
