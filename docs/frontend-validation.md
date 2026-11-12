# Validación del rediseño — 2026-11-11

## Resultado

| Comprobación | Resultado |
| --- | --- |
| Compilación TypeScript estricta y Vite | Correcta |
| Pruebas Python, incluyendo contratos API | 108 pasaron |
| React Testing Library / Vitest | 11 pasaron |
| Playwright escritorio 1440×1000 y móvil 390×844 | 10 pasaron |
| Frontend compilado + FastAPI/OpenCV/YOLO/CUDA reales | 1 prueba integrada pasó |

Las pruebas anteriores ligadas a `app.js`, `monitor.js`, `dashboard.js` y
`camera.js` fueron reemplazadas por pruebas de React y recorridos de navegador,
porque esos archivos ya no forman parte de la interfaz. Los contratos de captura,
modelo, API, SQLite, informes y WebSocket siguen cubiertos por pytest.
Hay una advertencia existente de Starlette/HTTPX en TestClient, sin fallos.

## Comportamientos comprobados

- Navegación entre las seis vistas, y alias `/`, `/dashboard`, `/monitor`.
- Assets compilados servidos por FastAPI; mensaje de compilación pendiente si no
  existe `dist/index.html`, manteniendo `/health` operativo.
- Estados vacíos, servidor desconectado, modelo ausente y controles de reintento.
- Búsqueda por etiquetas españolas y filtros de resultado/fecha en los registros
  cargados; apertura/cierre de detalles y ausencia de datos históricos explícita.
- Selección de fuente y dispositivo, inicio, parada y ajuste de confianza.
- Reutilización del UUID de captura USB al perder la primera respuesta.
- Cámara del navegador con dispositivo sintético: iniciar/detener, análisis de
  preview separado, captura manual y subida de imagen.
- “Sin detecciones” mantiene la calidad sin verificar; `PASS` histórico no se
  presenta como aprobación actual. Los porcentajes conservan su significado.
- Diseño inspeccionado en capturas de escritorio/móvil; comprobación automática
  de ausencia de desbordamiento horizontal de página en cada vista. Las tablas
  se desplazan dentro de su contenedor.

La comprobación de cámara del navegador detectó una espera de `video.play()`
mientras el video seguía oculto. Se corrigió mostrando el video antes de esperar
la reproducción. Se añadió liberación de pistas cuando un permiso se resuelve
después de cambiar de vista. El recorrido de navegador pasó tras el cambio.

## Integración con GPU real

Se sirvió el build con una copia temporal del backend en el puerto 8011, su propia
SQLite y su carpeta de capturas. Los pesos de validación existentes se leyeron
sin modificarlos. La fuente fue `outputs/demo/sample.avi`, de contenido sintético.
No se escribieron inspecciones de prueba en `outputs/inspections.db` del usuario.

La prueba verificó:

1. Modelo cargado y frontend compilado disponible por HTTP real.
2. Inicio de la demo con dispositivo CUDA y fotogramas procesados por OpenCV/YOLO.
3. Estadísticas con **cero** inspecciones mientras sólo había vista previa.
4. Captura explícita con **una** inspección, descarga de original y anotada.
5. Estado del backend con `inference_device=cuda:0`.
6. Umbral actualizado a 0.65 y detención confirmada de la captura.
7. Registro disponible en la vista Historial de la instancia temporal.

Los tiempos mostrados en la captura de pantalla son lecturas de esa sesión, no
un benchmark de rendimiento. La demo no es evidencia de precisión sobre piezas.

SHA-256 de los pesos anteriores, conservado:
`621c742492ffe5137d214893499e47d59066685c53c400810de71cd26e4f8bac`.

## Evidencia local

| Archivo | Contenido |
| --- | --- |
| `outputs/frontend-redesign/desktop-inspection.png` | Inspección, estado inicial |
| `outputs/frontend-redesign/mobile-inspection.png` | Adaptación móvil |
| `outputs/frontend-redesign/desktop-overview.png` | Panel general con fixtures de prueba |
| `outputs/frontend-redesign/mobile-overview.png` | Panel general móvil con fixtures |
| `outputs/frontend-redesign/desktop-capture-fixture.png` | Captura e interfaz con datos sintéticos identificados |
| `outputs/frontend-redesign/mobile-capture-fixture.png` | Resultado de captura en móvil con fixtures |
| `outputs/frontend-redesign/real-stack-demo.png` | FastAPI y YOLO reales con video sintético |
| `outputs/frontend-redesign/desktop-overview-live.png` | Build final con estadísticas reales del backend local, consultas de sólo lectura |
| `outputs/frontend-redesign/desktop-inspection-live.png` | Estación del build final servida por FastAPI, sin iniciar captura |
| `outputs/frontend-python-tests.log` | Resultado de pytest |
| `outputs/frontend-e2e.log` | Recorridos Playwright de escritorio/móvil |
| `outputs/frontend-real-e2e.log` | Integración real de la instancia aislada |
| `outputs/frontend-real-server.log` | Log del servidor aislado |

Los fixtures se restringen a pruebas; la aplicación de producción sólo consulta
el backend. Estas imágenes y logs no se suben a Git. Las capturas del panel con
fixtures no representan conteos ni precisión de la operación real.

## Pendientes y límites

- No se volvió a probar una webcam USB física ni un teléfono físico en esta
  sesión. Se verificaron los controles mediante contratos y el video de demo
  real, y `getUserMedia` mediante un dispositivo sintético de navegador.
- Historial sin imágenes, fuente, modelo o todas las cajas: el contrato actual no
  devuelve esos datos. Se documenta en el detalle, sin modificar SQLite.
- Filtros locales sobre el límite cargado; no hay búsqueda global ni paginación
  de servidor. La tendencia no devuelve fecha completa y se etiqueta en UTC.
- Selección de archivo de modelo, IoU y tamaño de inferencia permanece en el
  arranque de FastAPI; no hay endpoints de escritura para esas opciones.
- Los nombres dibujados dentro de las imágenes por YOLO conservan las clases del
  modelo. Las etiquetas, controles y resultados de la interfaz están en español.
- Una pieza sin detecciones no está aprobada automáticamente; no se evaluó
  precisión sobre nuevas piezas ni se ejecutó entrenamiento.

Comandos y arquitectura: [frontend-redesign.md](frontend-redesign.md).

## Actualización de temas claro/oscuro

Selector accesible en la barra superior, preferencia persistente y funcionamiento
con almacenamiento restringido. Pruebas actualizadas: 15 casos de React/Vitest y
14 recorridos Playwright (escritorio y móvil). Se comprueba la persistencia tras
recargar, la navegación en claro, ausencia de desbordamiento y contraste mínimo
4.5:1 en título, descripción de panel y botón primario. Las capturas de ambos
temas se revisaron visualmente. No se cambian cámara, inferencia ni SQLite.
La prueba de `getUserMedia` utiliza un MediaStream sintético de canvas para
evitar bloqueos intermitentes del dispositivo ficticio de Edge; sigue ejercitando
reproducción, captura a Blob, subida y detención de pistas nativas.
