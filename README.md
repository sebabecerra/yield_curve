# Yield Curve Analytics

## Resumen

Este repositorio contiene una plataforma estática de analítica de curva de tasas diseñada para estimar, comparar, visualizar y descargar estructuras temporales de tasas de interés directamente en el navegador. La versión activa del proyecto vive en [`api_js/`](/Users/sbc/projects/yiled_curve/api_js) y está pensada para publicarse en GitHub Pages sin backend operativo.

La aplicación toma una base de mercado ya incorporada en el sitio, normaliza las series, construye curvas mediante modelos paramétricos y no paramétricos, deriva curvas forward y agrega un módulo de proyección simple sobre factores Nelson-Siegel. Además, incluye una pestaña adicional de `Dynamic Nelson-Siegel` con filtro de Kalman bajo una formulación parsimoniosa de espacio de estados.

En términos prácticos, la herramienta busca resolver cuatro necesidades:

1. traducir una base de tasas observadas en curvas continuas comparables por fecha;
2. ofrecer una lectura ejecutiva de nivel, pendiente, curvatura y forwards;
3. permitir descargas inmediatas de curvas, forwards y datos limpios;
4. mantener una arquitectura extremadamente simple de despliegue: HTML, CSS y JavaScript puro.

---

## 1. Objetivo del proyecto

La motivación principal de este proyecto es convertir lógica cuantitativa típicamente encapsulada en notebooks o scripts de análisis en una experiencia web pública, bilingüe y de baja fricción.

La aplicación está orientada a:

- monitoreo de mercado;
- discusión comercial y ejecutiva;
- análisis comparativo de cambios de curva;
- exploración metodológica de modelos de estructura temporal;
- visualización de curvas spot y curvas forward;
- prototipado de herramientas de renta fija sin infraestructura backend.

La hipótesis de diseño es simple: para un conjunto relativamente pequeño de series clave, una base de tasas real puede incrustarse en un sitio estático y usarse para estimación local sin sacrificar demasiado valor analítico en el frente visual y exploratorio.

---

## 2. Arquitectura activa

La carpeta activa del proyecto es:

- [`api_js/`](/Users/sbc/projects/yiled_curve/api_js)

Archivos principales:

- [`api_js/index.html`](/Users/sbc/projects/yiled_curve/api_js/index.html)
- [`api_js/index_en.html`](/Users/sbc/projects/yiled_curve/api_js/index_en.html)
- [`api_js/css/styles.css`](/Users/sbc/projects/yiled_curve/api_js/css/styles.css)
- [`api_js/js/app.js`](/Users/sbc/projects/yiled_curve/api_js/js/app.js)
- [`api_js/js/models.js`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)
- [`api_js/data/market_rows.js`](/Users/sbc/projects/yiled_curve/api_js/data/market_rows.js)
- [`api_js/data/market_rates.csv`](/Users/sbc/projects/yiled_curve/api_js/data/market_rates.csv)

Estructura:

```text
api_js/
  index.html
  index_en.html
  css/
    styles.css
  js/
    app.js
    models.js
  data/
    market_rows.js
    market_rates.csv
```

La aplicación:

- corre 100% en frontend;
- no requiere backend para estimar;
- puede publicarse directamente en GitHub Pages;
- opera con una base real embebida;
- expone una UI bilingüe ES/EN;
- permite descarga de datos y resultados sin persistencia del lado servidor.

---

## 3. Datos y universo de tasas

La base incrustada representa una selección de nodos de mercado expresados como tasas anuales por madurez:

- `TPM`
- `SPC_03Y`
- `SPC_06Y`
- `SPC_1Y`
- `SPC_2Y`
- `SPC_3Y`
- `SPC_4Y`
- `SPC_5Y`
- `SPC_10Y`

La correspondencia entre nombre y madurez en meses se codifica en [`api_js/js/models.js`](/Users/sbc/projects/yiled_curve/api_js/js/models.js):

```text
M = {1, 3, 6, 12, 24, 36, 48, 60, 120}
```

En la implementación, estas madureces viven en el objeto `RATE_MONTHS`.

La base tabular original está en:

- [`api_js/data/market_rates.csv`](/Users/sbc/projects/yiled_curve/api_js/data/market_rates.csv)

La base consumida directamente por el navegador está en:

- [`api_js/data/market_rows.js`](/Users/sbc/projects/yiled_curve/api_js/data/market_rows.js)

Esto permite que la app:

- no solicite archivos al usuario;
- no dependa de `fetch` a servicios externos;
- mantenga tiempos de carga bajos;
- sea completamente compatible con hosting estático.

---

## 4. Normalización y limpieza

La carga de datos ocurre en [`api_js/js/app.js`](/Users/sbc/projects/yiled_curve/api_js/js/app.js), donde se ejecutan tres pasos:

### 4.1 Normalización de aliases

Se mapean nombres legacy a aliases internos. Por ejemplo:

```text
spc_pesos_2y -> SPC_2Y
```

Esto evita depender del nombre exacto original de la serie.

### 4.2 Conversión de tipos

Cada columna distinta de `Date` se convierte a numérico:

```text
x[t,m] =
  float(v)   si v es parseable
  NaN        si v es vacío o inválido
```

### 4.3 Selección de fechas completas

Dado un subconjunto de columnas \( C \), la fecha \( t \) se considera usable si:

```text
para todo c en C, x[t,c] pertenece a R
```

En la práctica, esto significa que cada modelo trabaja sobre el subconjunto de fechas completas para las series efectivamente seleccionadas por el usuario.

---

## 5. Notación general

Sea:

- `tau`: madurez en años
- `m`: madurez en meses
- `y_t(tau)`: tasa spot observada o estimada en la fecha `t` para la madurez `tau`
- `beta_t`: vector de factores latentes o coeficientes del modelo
- `lambda`: parámetro de decaimiento
- `epsilon_t`: error de medición
- `eta_t`: ruido de transición de estado

Cuando la app reconstruye una curva mensual, se usa:

```text
tau = m / 12
```

para \( m = 1, 2, \dots, 120 \).

---

## 6. Modelo Nelson-Siegel

### 6.1 Especificación

La forma funcional clásica es:

```text
y_t(tau) =
  beta_1,t
  + beta_2,t * ((1 - exp(-lambda * tau)) / (lambda * tau))
  + beta_3,t * (((1 - exp(-lambda * tau)) / (lambda * tau)) - exp(-lambda * tau))
```

donde:

- `beta_1,t`: nivel
- `beta_2,t`: pendiente
- `beta_3,t`: curvatura

### 6.2 Cargas factoriales

Definimos:

```text
L(tau, lambda) = (1 - exp(-lambda * tau)) / (lambda * tau)
C(tau, lambda) = L(tau, lambda) - exp(-lambda * tau)
```

Entonces:

```text
y_t(tau) = beta_1,t + beta_2,t * L(tau, lambda) + beta_3,t * C(tau, lambda)
```

### 6.3 Estimación

Para cada fecha \( t \), se construye una matriz de diseño:

```text
X_t =
[1, L(tau_1,lambda), C(tau_1,lambda)]
[1, L(tau_2,lambda), C(tau_2,lambda)]
...
[1, L(tau_n,lambda), C(tau_n,lambda)]
```

y un vector de tasas observadas:

```text
y_t = [y_t(tau_1), y_t(tau_2), ..., y_t(tau_n)]'
```

Los betas se obtienen por mínimos cuadrados ordinarios:

```text
beta_hat_t = (X_t' X_t)^(-1) X_t' y_t
```

### 6.4 Implementación

La lógica está en:

- [`fitNelsonSiegel(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)
- [`reconstructNelsonSiegelCurve(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)

---

## 7. Modelo Nelson-Siegel-Svensson

### 7.1 Especificación

Svensson agrega una segunda curvatura:

```text
y_t(tau) =
  beta_1,t
  + beta_2,t * L(tau, lambda_1)
  + beta_3,t * C1(tau, lambda_1)
  + beta_4,t * C2(tau, lambda_2)
```

donde:

```text
C1(tau, lambda_1) = (1 - exp(-lambda_1 * tau)) / (lambda_1 * tau) - exp(-lambda_1 * tau)
C2(tau, lambda_2) = (1 - exp(-lambda_2 * tau)) / (lambda_2 * tau) - exp(-lambda_2 * tau)
```

### 7.2 Interpretación

Este modelo permite capturar formas más flexibles de curva, especialmente cuando la curvatura presenta dos zonas distintas de máximo o cuando la parte media y larga de la curva requieren grados adicionales de libertad.

### 7.3 Estimación

Análogamente a Nelson-Siegel, para cada fecha:

```text
beta_hat_t = (X_t' X_t)^(-1) X_t' y_t
```

pero ahora con cuatro columnas en `X_t`.

### 7.4 Implementación

La lógica está en:

- [`fitSvensson(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)
- [`reconstructSvenssonCurve(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)

---

## 8. Cubic spline natural

### 8.1 Idea general

En vez de imponer una estructura paramétrica de factores, el spline cúbico natural interpola una función suave entre los nodos observados.

Sea un conjunto de nodos:

```text
(tau_1, y_1), (tau_2, y_2), ..., (tau_n, y_n)
```

Se busca una función \( s(\tau) \) tal que en cada tramo \( [\tau_i, \tau_{i+1}] \):

```text
s_i(tau) = a_i + b_i * (tau - tau_i) + c_i * (tau - tau_i)^2 + d_i * (tau - tau_i)^3
```

sujeta a:

1. continuidad en nivel;
2. continuidad en primera derivada;
3. continuidad en segunda derivada;
4. condición natural en extremos:

```text
s''(tau_1) = 0
s''(tau_n) = 0
```

### 8.2 Implementación

La rutina está en:

- [`naturalCubicSpline(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)

Es útil cuando se quiere una curva suave que pase por los puntos observados sin imponer interpretación económica estricta a factores latentes.

---

## 9. Curvas forward

### 9.1 Definición discreta

A partir de una curva spot discreta, la app construye una curva forward entre meses consecutivos usando capitalización discreta:

```text
f(t1, t2) = (( (1 + z(t2))^t2 / (1 + z(t1))^t1 )^(1 / (t2 - t1))) - 1
```

donde:

- `z(t1)` y `z(t2)` son tasas spot anualizadas
- `t1` y `t2` están medidos en años
- en la implementación se usa \( t_2=t_1+\frac{1}{12} \).

En la implementación:

```text
t2 = t1 + 1/12
```

### 9.2 Interpretación

La curva forward no muestra fechas calendario sino madurez forward mensual implícita por la curva estimada. En consecuencia:

- el eje X es madurez en meses;
- la leyenda distingue la fecha base y, cuando aplica, el horizonte proyectado.

### 9.3 Implementación

La rutina está en:

- [`forwardCurveFromSpot(...)`](/Users/sbc/projects/yiled_curve/api_js/js/app.js)

---

## 10. Proyección AR(1) sobre factores Nelson-Siegel

### 10.1 Motivación

Para agregar una capa simple de forecast, la app toma los factores históricos de Nelson-Siegel y les ajusta una dinámica autoregresiva independiente.

### 10.2 Modelo

Para cada factor \( x_t \in \{\text{level},\text{slope},\text{curvature}\} \):

```text
x_t = a + phi * x_(t-1) + epsilon_t
```

con:

```text
epsilon_t ~ (0, sigma^2)
```

### 10.3 Proyección

Dado el último valor observado \( x_T \), la proyección recursiva a \( h \) pasos es:

```text
x_hat_(T+1) = a + phi * x_T
x_hat_(T+2) = a + phi * x_hat_(T+1)
...
x_hat_(T+h) = a + phi * x_hat_(T+h-1)
```

### 10.4 Reconstrucción de curva

Una vez obtenidos los factores proyectados:

```text
beta_hat_(T+h) = [beta_1,(T+h), beta_2,(T+h), beta_3,(T+h)]'
```

la curva proyectada se obtiene mediante la misma ecuación Nelson-Siegel:

```text
y_hat_(T+h)(tau) =
  beta_1,(T+h)
  + beta_2,(T+h) * L(tau, lambda)
  + beta_3,(T+h) * C(tau, lambda)
```

### 10.5 Implementación

Rutinas relevantes:

- [`fitAr1Series(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)
- [`projectAr1Series(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)
- lógica de UI en [`plotProjection()`](/Users/sbc/projects/yiled_curve/api_js/js/app.js)

Horizontes disponibles:

- `1M`
- `3M`
- `6M`
- `12M`

La app muestra:

- curva actual estimada;
- curva observada de la fecha base;
- curvas proyectadas activadas por el usuario;
- curvas forward correspondientes.

---

## 11. Dynamic Nelson-Siegel con filtro de Kalman

### 11.1 Motivación

El ajuste estático fecha a fecha puede producir factores más ruidosos que los deseables para un análisis dinámico. La pestaña `Kalman` introduce una formulación simplificada de espacio de estados que suaviza los factores latentes en el tiempo.

### 11.2 Ecuación de medición

Sea:

```text
y_t = H(lambda) * alpha_t + epsilon_t
```

donde:

- `y_t`: vector de tasas observadas por madurez en la fecha `t`
- `alpha_t = [beta_1,t, beta_2,t, beta_3,t]'`: estado latente
- `H(lambda)`: matriz de cargas Nelson-Siegel
- `epsilon_t ~ N(0, R)`: error de medición

### 11.3 Ecuación de transición

Se usa una transición diagonal:

```text
alpha_t = c + F * alpha_(t-1) + eta_t
```

con:

```text
F =
[phi_1, 0,     0]
[0,     phi_2, 0]
[0,     0,     phi_3]
```

y:

```text
eta_t ~ N(0, Q)
```

donde \( Q \) también se toma diagonal en esta implementación.

### 11.4 Estimación de parámetros auxiliares

La implementación actual procede en dos etapas:

1. ajusta Nelson-Siegel estático por fecha y obtiene una trayectoria OLS de betas;
2. estima un `AR(1)` independiente sobre cada beta para construir:
   - \( c \)
   - \( F \)
   - \( Q \)

El error de medición se aproxima usando la varianza residual cross-sectional del ajuste OLS:

```text
R = diag(sigma_hat_tau1^2, ..., sigma_hat_taun^2)
```

### 11.5 Filtro de Kalman

Predicción:

```text
a_(t|t-1) = c + F * a_(t-1|t-1)
P_(t|t-1) = F * P_(t-1|t-1) * F' + Q
```

Innovación:

```text
v_t = y_t - H * a_(t|t-1)
S_t = H * P_(t|t-1) * H' + R
```

Ganancia de Kalman:

```text
K_t = P_(t|t-1) * H' * S_t^(-1)
```

Actualización:

```text
a_(t|t) = a_(t|t-1) + K_t * v_t
P_(t|t) = (I - K_t * H) * P_(t|t-1)
```

### 11.6 Suavizado

La app además aplica un backward smoothing tipo Rauch-Tung-Striebel:

```text
J_t = P_(t|t) * F' * P_(t+1|t)^(-1)
a_(t|T) = a_(t|t) + J_t * (a_(t+1|T) - a_(t+1|t))
```

### 11.7 Resultado

La pestaña `Kalman` entrega:

- curva spot filtrada/suavizada;
- curva forward filtrada;
- comparaciones por fecha bajo una señal latente menos ruidosa que la obtenida con OLS fecha a fecha.

### 11.8 Implementación

Rutina principal:

- [`fitDynamicNelsonSiegelKalman(...)`](/Users/sbc/projects/yiled_curve/api_js/js/models.js)

UI:

- [`api_js/index.html`](/Users/sbc/projects/yiled_curve/api_js/index.html)
- [`api_js/index_en.html`](/Users/sbc/projects/yiled_curve/api_js/index_en.html)
- [`plotModel("kf")`](/Users/sbc/projects/yiled_curve/api_js/js/app.js)

Notebook de validación:

- [`old/notebooks/dynamic_nelson_siegel_kalman.ipynb`](/Users/sbc/projects/yiled_curve/old/notebooks/dynamic_nelson_siegel_kalman.ipynb)

### 11.9 Advertencia metodológica

Esta implementación no pretende ser un `Dynamic Nelson-Siegel` institucional completo. Es una aproximación parsimoniosa y útil para exploración, pero:

- usa transición diagonal;
- calibra \( Q \) y \( R \) a partir de etapas auxiliares;
- no realiza máxima verosimilitud completa del sistema;
- no incorpora shocks macro ni restricciones adicionales.

Su valor está en entregar una primera capa dinámica interpretable y usable en frontend.

---

## 12. Descargas

La aplicación permite descargar:

- datos limpios;
- curvas spot;
- curvas forward;
- proyecciones por horizonte.

En general, cada descarga genera un CSV temporal desde el navegador mediante `Blob` y `ObjectURL`.

La utilidad central está en [`setDownloadLink(...)`](/Users/sbc/projects/yiled_curve/api_js/js/app.js).

---

## 13. Interfaz y experiencia de uso

La interfaz fue diseñada con una lógica de “terminal analítica”:

- fondo casi negro;
- jerarquía visual compacta;
- tabs superiores;
- panel lateral de controles;
- panel derecho de gráficos;
- español e inglés desde páginas separadas.

Pestañas disponibles:

- `Modelo`
- `Datos`
- `Nelson-Siegel`
- `Kalman`
- `Svensson`
- `Cubic spline`
- `Proyección`

---

## 14. Cómo correr localmente

```bash
cd /Users/sbc/projects/yiled_curve/api_js
python3 -m http.server 8080
```

Luego abre:

- [http://127.0.0.1:8080/index.html](http://127.0.0.1:8080/index.html)
- [http://127.0.0.1:8080/index_en.html](http://127.0.0.1:8080/index_en.html)

---

## 15. Despliegue

GitHub Pages se publica mediante:

- [/.github/workflows/deploy-pages.yml](/Users/sbc/projects/yiled_curve/.github/workflows/deploy-pages.yml)

Ese workflow despliega:

```yaml
path: ./api_js
```

Flujo normal:

```bash
cd /Users/sbc/projects/yiled_curve
git add api_js README.md
git commit -m "update api_js"
git push origin main
```

URL pública:

- [https://sebabecerra.github.io/yield_curve/](https://sebabecerra.github.io/yield_curve/)

---

## 16. Limitaciones

### 16.1 Datos

- la base está embebida y no se actualiza automáticamente;
- no hay refresh en tiempo real desde proveedor externo;
- la app no pretende reemplazar una infraestructura de mercado en línea.

### 16.2 Modelos

- Nelson-Siegel y Svensson usan mínimos cuadrados cross-sectional;
- la proyección AR(1) es deliberadamente simple;
- el módulo Kalman es parsimonioso, no una implementación institucional completa.

### 16.3 Arquitectura

- no existe backend;
- no existe persistencia de usuario;
- no existe autenticación;
- toda la lógica y los datos activos viven del lado cliente.

---

## 17. Estado del repositorio

La app activa es `api_js/`. El resto del trabajo histórico se conserva en:

- [`old/`](/Users/sbc/projects/yiled_curve/old)

Ahí quedan implementaciones anteriores, notebooks, backends y prototipos que ya no son la ruta principal de publicación.

---

## 18. Recomendación operativa

Para mantener el repositorio limpio:

- no uses `git add .`
- usa `git add api_js README.md`
- revisa `git status` antes de commitear
- evita subir archivos grandes o materiales locales desde `papers/`

---

## 19. Conclusión

Este proyecto no busca ser un motor institucional cerrado de pricing ni una plataforma enterprise de renta fija. Su foco es otro: convertir una base real de tasas y un conjunto de modelos estándar de estructura temporal en una herramienta web clara, rápida y visualmente sólida.

Su valor está en el puente que construye entre:

- analítica cuantitativa;
- visualización ejecutiva;
- simplicidad de despliegue;
- prototipado serio de productos financieros.

En ese sentido, la plataforma funciona simultáneamente como:

- herramienta de análisis;
- demostración de producto;
- entorno pedagógico de modelos de curva;
- punto de partida para extensiones futuras más avanzadas.
