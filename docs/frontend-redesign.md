# Frontend de Acero Cifrado

## Base y alcance

`feat/frontend-redesign` parte de `master` / `origin/master`, commit `de65195`,
con el árbol limpio. No incorpora la rama del dataset. React + TypeScript + Vite
reemplaza los HTML y scripts anteriores con una sola aplicación.

No se cambian entrenamiento, inferencia, pesos ni SQLite. Los únicos cambios de
ejecución en Python son el directorio estático `frontend/dist`, la entrega del
mismo HTML en `/`, `/dashboard` y `/monitor`, y un error explicativo si falta el build.

## Iniciar en PowerShell

Comprobado con Node.js 24.14.0, npm 11.13.0 y el Python del entorno virtual
existente. `package-lock.json` fija las dependencias de npm. Desde la raíz:

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
# Sólo si aún no está preparado el entorno Python
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:ACERO_MODEL_PATH = 'model/steel-defect-yolo11n.pt'
$env:ACERO_DEVICE = 'auto'
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Abre [Inspección](http://127.0.0.1:8000/). Los enlaces anteriores
[/dashboard](http://127.0.0.1:8000/dashboard) y
[/monitor](http://127.0.0.1:8000/monitor) abren las vistas correspondientes de la
misma aplicación. Para el teléfono, usa `--host 0.0.0.0` y la IP local del equipo;
su cámara requiere HTTPS fuera de localhost. La cámara USB del servidor no
requiere permisos de cámara del navegador. Se conserva la configuración HTTPS
existente del README.

`dist/` no se versiona: compilar al clonar/cambiar de rama y reiniciar FastAPI
después de migrar. `/health` comprueba el backend; `model_loaded` indica si hay
pesos cargados. La aplicación no descarga modelos automáticamente.

### Desarrollo con recarga

Mantén FastAPI en el puerto 8000. En otra terminal:

```powershell
npm --prefix frontend run dev
```

Abre [Vite](http://localhost:5173/static/). Su proxy reenvía HTTP, MJPEG, descargas
y WebSocket a FastAPI. Para otro puerto, configura `ACERO_BACKEND_URL` antes de
iniciar Vite. `vite preview` sólo sirve assets y no sustituye el backend integrado.

## Arquitectura y diseño

```text
frontend/src/
  App.tsx                 navegación y recursos compartidos
  types.ts                contratos tipados
  format.ts               etiquetas en español, fechas y filtros
  services/api.ts         HTTP, multipart y errores
  hooks/useResource.ts    consultas y estados de carga/error
  hooks/useCamera.ts      sesión USB, parámetros y captura idempotente
  hooks/useMonitor.ts     WebSocket y reconexión
  components/             controles, resultados, tablas, gráficas y estados
  views/                  inspección, panel, historial, estadísticas y configuración
  tokens.css              colores y tipografía
  styles.css              composición y adaptación móvil
```

La navegación usa `#inspeccion`, `#resumen`, `#historial`, `#estadisticas`,
`#configuracion` y `#monitor`: no colisiona con los endpoints y no necesita otro
router. No hay una interfaz antigua en paralelo. La sesión USB permanece en el
servidor y se vuelve a adjuntar al recargar; la cámara del navegador se libera al
detenerla o salir, incluso si el permiso llega tarde. No hay imágenes en localStorage.

La cámara domina el área de trabajo y el resultado registrado queda a su derecha.
Se usan superficies grafito/acero, cian suave, verde grisáceo y ámbar; el rojo se
reserva para errores. Manrope se incluye localmente, con licencia SIL OFL en
`/static/licenses/manrope.txt`; no depende de Google Fonts/CDN. Iconos Lucide,
gráficas SVG y CSS sin una plantilla ni librería de gráficas. Las traducciones
conservan las clases y severidades originales en API/SQLite.

Hay foco de teclado, estados de carga, errores con reintento, movimiento reducido,
tablas desplazables en móvil y un diálogo nativo con cierre por Escape. Los datos
faltantes aparecen como no disponibles y no se completan con valores inventados.

## Contratos y significado de los datos

| Función | Contrato existente |
| --- | --- |
| Disponibilidad y hardware | `GET /health`, `GET /runtime` |
| Buscar cámaras | `GET /cameras?backend=...` |
| Iniciar/detener fuente USB o demo | `POST /camera/start`, `POST /camera/stop` |
| Estado y vista previa | `GET /camera/status`, `GET /camera/stream` |
| Umbral de la sesión | `POST /camera/settings` con `{conf}` |
| Registrar captura USB | `POST /camera/capture` con UUID `request_id` |
| Vista previa del navegador | `POST /preview?conf=...&device=...` |
| Captura del navegador/imagen | `POST /detect`, `POST /upload`, multipart |
| Resultados remotos | `WS /ws/monitor` |
| Historial | `GET /history?limit=50|100|250|500` |
| Resumen y tendencias | `GET /stats`, `GET /trend?bucket_seconds=...&limit_buckets=30` |
| Descargas | `GET /captures/{filename}`, `/export/csv`, `/export/pdf` |

La vista previa **no registra inspecciones**. La captura USB reutiliza el UUID
cuando pierde una respuesta de red. `/detect` y `/upload` no ofrecen idempotencia;
el navegador no reintenta automáticamente esos POST.

“Sin detecciones” no significa aprobación. `PASS` se presenta como histórico sin
verificar. La confianza promedio viene de todas las detecciones guardadas y no
mide precisión. La tasa de hallazgos cuenta inspecciones; la distribución por
tipo cuenta detecciones. La severidad es una regla orientativa, no medición física.

La tendencia contiene los últimos intervalos **con actividad** del servidor, con
etiquetas UTC HH:MM; no ofrece fecha completa. Los huecos no se representan a
escala temporal. El historial sí devuelve ISO UTC y usa fechas/horas locales del
navegador para presentación y filtros.

## Límites que conserva esta fase de frontend

- Los filtros y búsqueda operan sobre los últimos registros cargados, no toda
  SQLite. Se indica el alcance; paginación local de 15 registros.
- `/history` sólo expone ID, fecha, resultado, cantidad, defecto principal,
  confianza principal y severidad. No ofrece fuente, nombre del modelo, todas las
  cajas ni imágenes por ID. El detalle lo explica; no se vinculan por conjeturas.
- La captura actual USB tiene enlaces originales/anotados reales. Las capturas
  del navegador usan Blob local y anotación de respuesta. Su resultado de sesión
  no constituye archivo histórico persistente.
- No hay endpoint para cambiar pesos, tamaño de inferencia o IoU: se consultan
  disponibilidad/clases y se conserva la configuración de arranque con variables
  existentes. No se muestra un selector de modelos que simule guardar cambios.
- OpenCV identifica fuentes por índice y puede incluir la cámara integrada. Su
  búsqueda puede tardar o encontrar dispositivos ocupados por otra aplicación.

## Pruebas y capturas

```powershell
npm --prefix frontend run build
npm --prefix frontend test
npm --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m pytest -q
```

Playwright usa Edge instalado en Windows y Chromium en otros sistemas. Opcional:

```powershell
cd frontend
npx playwright install chromium
$env:PLAYWRIGHT_CHANNEL = 'chromium'
npm run test:e2e
cd ..
```

React Testing Library reemplaza los dobles DOM de los scripts retirados. Los E2E
verifican navegación, filtros, detalle, adaptación, CPU/GPU, inicio/parada, umbral,
idempotencia, errores, estados vacíos, cámara del navegador y subida. Las pruebas
visuales usan fixtures y cámara sintética del navegador: sus cifras no son métricas
operativas. El reporte final está en [frontend-validation.md](frontend-validation.md).

### Integración real con historial aislado

Si falta el video, generar `outputs/demo/sample.avi` con `tools/create_test_media.py`.
Con el build y los pesos existentes, en una terminal:

```powershell
.\.venv\Scripts\python.exe tools/serve_frontend_smoke.py --model model/steel-defect-yolo11n.pt --device cuda
```

En otra terminal:

```powershell
$env:ACERO_REAL_SMOKE = '1'
npm --prefix frontend run test:e2e -- --project=desktop
Remove-Item Env:ACERO_REAL_SMOKE
```

El host copia la app a un directorio temporal con SQLite y capturas propias; usa
FastAPI, OpenCV y YOLO reales con la demo sintética. Comprueba contador cero en
preview, uno al capturar, descarga, CUDA, umbral y detención. No prueba precisión
sobre piezas ni una webcam USB/teléfono físicos. Terminar el host con Ctrl+C.

Las capturas se guardan localmente en `outputs/frontend-redesign/` y los logs en
`outputs/frontend-*.log`. Los fixtures visuales indican su origen sintético;
`real-stack-demo.png` muestra YOLO real sobre la demo. No se publican imágenes,
pesos, SQLite, node_modules ni dist en Git.
