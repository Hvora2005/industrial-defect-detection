# Acero Cifrado — inspección visual de piezas metálicas

Adaptación universitaria de [Hvora2005/industrial-defect-detection](https://github.com/Hvora2005/industrial-defect-detection).
Esta fase prepara la captura con webcam USB y archivos locales en Windows, conservando
la captura desde el teléfono, FastAPI, YOLO11, el monitor y el historial originales.
No incluye entrenamiento nuevo, ESP32 ni controles de motores.

**El clon no incluye pesos entrenados ni dataset.** Es posible probar la captura sin ellos;
la inspección de defectos requiere un archivo `model/best.pt` previamente entrenado.
Una vista previa nunca devuelve PASS/FAIL ni registra inspecciones.

## Repositorio del equipo y origen

El repositorio de trabajo de **Acero Cifrado** es
[Ghost3119/industrial-defect-detection](https://github.com/Ghost3119/industrial-defect-detection),
un fork oficial de
[Hvora2005/industrial-defect-detection](https://github.com/Hvora2005/industrial-defect-detection).
La rama principal conserva el nombre original: `master`. Se mantiene el historial del
proyecto y la relación de fork en GitHub.

| Remoto | Destino | Uso |
|---|---|---|
| `origin` | [Ghost3119/industrial-defect-detection](https://github.com/Ghost3119/industrial-defect-detection) | Publicar el trabajo del equipo |
| `upstream` | [Hvora2005/industrial-defect-detection](https://github.com/Hvora2005/industrial-defect-detection) | Consultar las actualizaciones del proyecto original |

La adaptación añade captura USB por OpenCV con selección y diagnóstico de cámaras,
pruebas con imágenes/videos locales, vista previa sin pesos y manejo explícito de la
ausencia del modelo en la API y la interfaz. Incluye pruebas automatizadas y esta guía de
Windows; conserva las fuentes originales, las reglas de detección, la licencia MIT y los
créditos de Hemin Vora.

Para verificar los remotos y consultar actualizaciones sin cambiar archivos locales:

```powershell
git remote -v
git fetch upstream
git log --oneline master..upstream/master
```

Publica los cambios del equipo en `origin`. El entorno virtual, los archivos `.env` y sus
variantes, certificados locales, dataset, pesos, cachés y resultados generados se excluyen
de Git; las imágenes de prueba se generan con el comando documentado más abajo.

## Arquitectura y revisión del repositorio

```text
Teléfono: getUserMedia → canvas → JPEG ──────────────┐
Galería del navegador: archivo → /upload ────────────┤
                                                   ▼
Webcam USB / imagen / video → backend/capture.py → POST /detect
                                                   │
                                  FastAPI → OpenCV (decodificación)
                                                   │
                                  detector.py → YOLO11 → PASS/FAIL
                                                   │
                      JSON + JPEG anotado + WebSocket /ws/monitor
                                                   │
                                 SQLite → historial, estadísticas, reportes
```

| Componente | Responsabilidad |
|---|---|
| `frontend/` | HTML, CSS y JavaScript sin compilación: captura, monitor y dashboard |
| `frontend/app.js` | `getUserMedia` con cámara trasera preferida; canvas a JPEG, máximo 640 px; captura manual, envío periódico cada 2 s y carga de imágenes |
| `backend/main.py` | FastAPI, rutas de inspección y páginas; difunde los resultados al monitor |
| `backend/capture.py` | Cliente OpenCV añadido: selección por índice, búsqueda de cámaras, imagen/video local y vista previa; reutiliza `/detect` |
| `backend/detector.py` | Carga los pesos una vez si existen; inferencia, cajas, severidad y regla original: cualquier detección implica FAIL |
| `backend/config.py` | Ruta absoluta de `model/best.pt`, confianza `0.4`, tamaño de inferencia `256`; `HOST`/`PORT` son referencias y el arranque se configura en Uvicorn |
| `backend/database.py` | SQLAlchemy y SQLite en `outputs/inspections.db` |
| `backend/reports.py` | Exportación CSV y PDF |
| `backend/generate_cert.py` | Certificado HTTPS local para la cámara del teléfono |
| `training/` | Conversión VOC→YOLO, entrenamiento e inferencia de muestra originales |
| `tools/create_test_media.py` | Genera imagen y video sintéticos para comprobar captura sin hardware |
| `tests/` | Pruebas de captura, errores, integración HTTP, historial y WebSocket sin pesos reales |

Antes de esta adaptación, OpenCV solamente decodificaba las imágenes subidas: no había
`VideoCapture` en el backend ni recepción de video continuo. El modo en vivo del teléfono
envía fotos periódicas. Estas fuentes y sus rutas siguen disponibles.

### Dependencias y YOLO11

- `requirements.txt` conserva las dependencias originales con versiones mínimas:
  Ultralytics (incluye PyTorch), OpenCV, NumPy y Pillow; FastAPI, Uvicorn, multipart,
  WebSockets y Jinja2; SQLAlchemy, fpdf2 y cryptography; utilidades de datos y entrenamiento.
- `requirements-dev.txt` añade pytest y HTTPX para probar la API. No se requiere Node.js.
- La vista previa gráfica necesita `opencv-python` con ventanas. `--headless` evita
  las ventanas; no instales simultáneamente distintas variantes de OpenCV.
- El entrenamiento original usa `yolo11n.pt` como base. `train.py` tiene valores por defecto
  de 80 épocas y 320 px; el README anterior describía una corrida de 60 épocas y 256 px.
  El backend conserva 256 px. No hay pesos, corridas ni métricas verificables en este clon.
- `model/` contiene únicamente `.gitkeep`. `dataset/data.yaml` se genera con el conversor y
  tampoco está incluido. `.gitignore` excluye pesos, dataset y resultados.
- Las clases originales de NEU-DET son `crazing`, `inclusion`, `patches`, `pitted_surface`,
  `rolled-in_scale` y `scratches`. El detector usa las clases almacenadas en los pesos.
  Un modelo genérico de COCO no sustituye un modelo de defectos. Las métricas del proyecto
  original no validan su desempeño sobre nuestras piezas estampadas.

Referencias: [Ultralytics](https://docs.ultralytics.com/quickstart/),
[PyTorch para Windows](https://pytorch.org/get-started/locally/) y
[OpenCV VideoCapture](https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html).

## Instalación en Windows (PowerShell)

Ejecuta todos los comandos desde la raíz del repositorio. Usa Python de 64 bits.
El intérprete del entorno virtual se invoca directamente para evitar depender de la
política de ejecución de scripts de PowerShell.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Para usar únicamente el sistema, instala `requirements.txt` en lugar del archivo de
desarrollo. La instalación inicial necesita internet; las capturas e inferencias con pesos
existentes son locales. Las versiones mínimas permiten que pip seleccione versiones nuevas,
por lo que la compatibilidad se debe comprobar en cada entorno.

Para usar solamente `capture.py --preview-only` y el generador de medios, basta instalar
OpenCV y NumPy en el entorno virtual; puedes posponer la descarga de PyTorch y del resto
del sistema hasta que necesites la API o la suite completa:

```powershell
.\.venv\Scripts\python.exe -m pip install "opencv-python>=4.10.0" "numpy>=1.26.0"
```

## Prueba inmediata sin hardware ni modelo

Genera un PNG y un video AVI/MJPG de 30 fotogramas. Son medios artificiales para verificar
lectura y transporte de imágenes, sin representar defectos reales ni medir precisión.

```powershell
.\.venv\Scripts\python.exe tools/create_test_media.py
.\.venv\Scripts\python.exe backend/capture.py --source outputs/demo/sample.png --preview-only
.\.venv\Scripts\python.exe backend/capture.py --source outputs/demo/sample.avi --preview-only
```

La imagen espera una tecla. En video o webcam, pulsa `q` o Escape, cierra la ventana o usa
Ctrl+C para terminar y liberar la captura. Los videos se leen secuencialmente hasta el final,
sin repetición automática ni sincronización con su FPS original. Cada imagen leída cuenta
como un fotograma, no como una pieza física.

Para una comprobación automática sin ventanas:

```powershell
.\.venv\Scripts\python.exe backend/capture.py --source outputs/demo/sample.png --preview-only --headless
.\.venv\Scripts\python.exe backend/capture.py --source outputs/demo/sample.avi --preview-only --headless --max-frames 10 --interval 0
```

La vista previa no requiere FastAPI. El código de salida es `0` al finalizar correctamente,
`1` ante errores, `2` con argumentos inválidos y `130` con Ctrl+C. La búsqueda devuelve `1`
si no encuentra ninguna cámara.

## Webcam USB y selección de cámara

Conecta la webcam y busca índices que entreguen una imagen:

```powershell
.\.venv\Scripts\python.exe backend/capture.py --list-cameras --max-index 5
.\.venv\Scripts\python.exe backend/capture.py --camera 0 --preview-only
```

Elige el índice devuelto por la búsqueda (`--camera 1`, por ejemplo). Se exploran los índices
cero a `--max-index`, inclusive, y la búsqueda puede tardar por los controladores. OpenCV
puede incluir la cámara integrada: el índice no identifica el tipo USB ni un nombre estable
y puede cambiar al reconectar. Esta fase usa una cámara a la vez, sin reconexión automática.

Si el controlador automático falla, repite búsqueda y captura con el mismo backend de Windows:

```powershell
.\.venv\Scripts\python.exe backend/capture.py --list-cameras --backend dshow
.\.venv\Scripts\python.exe backend/capture.py --camera 0 --backend dshow --preview-only
# Alternativa: sustituir dshow por msmf
```

## Arrancar la API e inspeccionar

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Abre [la interfaz](http://127.0.0.1:8000/), [el monitor](http://127.0.0.1:8000/monitor),
[el dashboard](http://127.0.0.1:8000/dashboard) o [la documentación API](http://127.0.0.1:8000/docs).
En otra terminal de PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Sin `model/best.pt`, las páginas abren y `/health` devuelve `model_loaded: false`;
`/detect` y `/upload` responden **503** con instrucciones, sin inventar ni guardar resultados.
Coloca pesos de defectos ya entrenados y de confianza en esa ruta y reinicia el servidor para
habilitar inferencia. Pesos inválidos o incompatibles producen un error al arrancar.
No ejecutes `training/train.py` en esta fase.

Con los pesos y el servidor disponibles, usa una segunda terminal:

```powershell
.\.venv\Scripts\python.exe backend/capture.py --camera 0
.\.venv\Scripts\python.exe backend/capture.py --source outputs/demo/sample.png
.\.venv\Scripts\python.exe backend/capture.py --source "C:\ruta con espacios\pieza.mp4" --headless --max-frames 10 --interval 0.5
```

Sin `--preview-only`, cada fotograma se envía como JPEG a `/detect`. Los resultados se
imprimen y la ventana muestra la imagen anotada de la API. El monitor recibe el resultado
por WebSocket y el dashboard consulta SQLite. Las pruebas con archivos **también quedan
en el historial**. `--interval` añade una pausa entre solicitudes (0.1 s por defecto), sin
garantizar una frecuencia. `--api-url http://127.0.0.1:8001` cambia el servidor; las solicitudes
esperan hasta 30 s y no se reintentan automáticamente.

### Teléfono: fuente original conservada

Para la cámara de un teléfono en la misma Wi-Fi necesitas HTTPS. Genera un certificado e
inicia un servidor HTTPS, por ejemplo en 8443:

```powershell
ipconfig
.\.venv\Scripts\python.exe backend/generate_cert.py --ip 192.168.1.14
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8443 --ssl-keyfile backend/certs/key.pem --ssl-certfile backend/certs/cert.pem
```

Sustituye la IP por la de tu computadora. Abre `https://<IP>:8443/` en el teléfono, acepta el
certificado local y concede acceso a la cámara. Revisa el Firewall de Windows si no conecta.
El cliente OpenCV usa HTTP en 8000 por defecto; si lo diriges a HTTPS, Python debe confiar
en el certificado. No se desactiva la verificación TLS.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_capture.py -q
```

Las pruebas generan y decodifican imágenes/videos reales en carpetas temporales y simulan
cámaras ausentes, desconexiones, selección, errores HTTP y cierre de recursos. La integración
comprueba el multipart contra FastAPI, los endpoints originales, SQLite temporal y WebSocket
con un detector simulado. **No valida inferencia YOLO ni hardware**.

El archivo original `training/test_inference.py` es un script manual, no una suite automatizada.
Requiere pesos y muestras reales para producir resultados:

```powershell
.\.venv\Scripts\python.exe training/test_inference.py --model model/best.pt --source "C:\ruta\imagenes" --conf 0.4
```

### Validación realizada en esta fase

Entorno comprobado: Windows 11 Home x64, Python 3.14.3, OpenCV 5.0.0
(`opencv-python` 5.0.0.93), FastAPI 0.162.4, Ultralytics 8.4.210 y PyTorch 2.15.0 CPU.
Otras combinaciones de versiones no se han verificado.

| Comprobación ejecutada | Resultado |
|---|---|
| `python -m pytest -q` | 50 pruebas pasaron; una advertencia de Starlette sobre el futuro reemplazo de HTTPX en TestClient |
| `python -m pip check` | Sin dependencias incompatibles declaradas |
| Generador y cliente con PNG y AVI/MJPG | Lectura correcta de 1 imagen y 30 fotogramas; límite de 10 fotogramas comprobado |
| Vista previa gráfica de PNG | Imagen visible en una ventana real de OpenCV; cierre con `q` comprobado |
| Cámara inexistente, índice 99 con DirectShow | Mensaje de conexión y salida 1, sin traceback |
| Uvicorn + petición HTTP real | Arranque correcto, `/health` sin modelo y `/detect` con 503; historial sin inspecciones |
| Navegador local | Interfaz con `MODEL MISSING`, monitor conectado y dashboard vacío |
| `node --check frontend/app.js` | Sintaxis válida; Node se usó para esta comprobación y no es necesario para ejecutar la aplicación |
| `pytest training/test_inference.py -q` | No contiene pruebas recolectables |
| Script original con `--model model/best.pt --source outputs/demo/sample.png` | Se detuvo con `FileNotFoundError`: faltan los pesos |

No se entrenó ni descargó ningún modelo. La captura USB real, su desconexión física,
la inferencia con pesos entrenados y la captura del teléfono siguen pendientes de validación.

### Comprobación manual pendiente

1. Sin hardware: genera los medios y abre ambas vistas previas. Inicia la API y comprueba
   `/health` y el error 503 mientras no haya pesos.
2. Con webcam: identifica el índice, observa la imagen, desconecta el USB durante la captura
   y confirma el error; reconecta y ejecuta de nuevo.
3. Con pesos existentes: inspecciona una imagen y una captura USB; verifica la imagen anotada
   en `/monitor` y el registro en `/dashboard`. Esto comprueba el flujo, no la precisión sobre
   piezas estampadas.
4. Si se utilizará el teléfono, comprueba permisos y captura por HTTPS en un teléfono real.

| Problema | Acción |
|---|---|
| No hay cámaras o no se abre un índice | Revisa USB, otro índice y `--max-index`; cierra Teams/Zoom/Cámara y permite cámara para aplicaciones de escritorio en Windows |
| La cámara deja de entregar imágenes | Revisa el cable, reconecta y repite; prueba `dshow` o `msmf` |
| No se abre un video | Comprueba ruta y codec; usa el AVI/MJPG generado como referencia |
| No conecta con la API | Arranca Uvicorn y revisa `--api-url`; para captura sin modelo usa `--preview-only` |
| HTTP 503 | Coloca pesos de defectos en `model/best.pt` y reinicia |
| La ventana no se abre | Comprueba `opencv-python` con GUI o usa `--headless` |

## API conservada

| Ruta | Método | Uso |
|---|---|---|
| `/health` | GET | Estado del servidor y presencia real del modelo |
| `/detect`, `/upload` | POST | JPEG/PNG multipart en el campo `file` |
| `/history`, `/stats`, `/trend` | GET | Historial, estadísticas y tendencia |
| `/export/csv`, `/export/pdf` | GET | Reportes |
| `/ws/monitor` | WebSocket | Difusión de cada inspección |

## Créditos y licencia

Proyecto original de **Hemin Vora**. Adaptación universitaria **Acero Cifrado**.
Se conserva la [licencia MIT](LICENSE).
