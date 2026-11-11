# Acero Cifrado — inspección visual de piezas metálicas

Adaptación universitaria de [Hvora2005/industrial-defect-detection](https://github.com/Hvora2005/industrial-defect-detection).
Incluye captura por webcam y archivos locales, inferencia CPU/CUDA y registro manual de
inspecciones en Windows. Conserva teléfono, FastAPI, YOLO11, monitor e historial originales.
No incluye entrenamiento nuevo, ESP32 ni controles de motores.

**El clon no incluye los pesos entrenados del autor ni el dataset.** Es posible probar la
captura sin ellos. En esta fase se validó un modelo de defectos de terceros, identificado
en la sección de inferencia; no se presenta como el modelo original de Hvora2005.
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
Windows; conserva las fuentes originales, la severidad, la licencia MIT y los
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
                                  detector.py → YOLO11 → detecciones / NO_DETECTIONS
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
| `backend/detector.py` | Comprueba clases NEU-DET y tarea, ejecuta inferencia, dibuja cajas, clases y confianza; emite `FAIL` o `NO_DETECTIONS` |
| `backend/config.py` | Pesos, tamaño, escala de grises e IoU configurables mediante `ACERO_*`; confianza por defecto `0.4`; el arranque se configura en Uvicorn |
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
- El contenido versionado de `model/` no incluye pesos. `dataset/data.yaml` se genera con el conversor y
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

Sin `--preview-only`, una imagen se envía como JPEG a `/detect` y registra una inspección.
Los videos y webcams del cliente CLI utilizan `/preview`: muestran inferencia sin registrar
cada fotograma como una pieza. Para registrar capturas manuales utiliza el dashboard.
Los resultados se imprimen y la ventana muestra la imagen anotada de la API. `--interval`
añade una pausa entre solicitudes (0.1 s por defecto), sin
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

## Inferencia YOLO con imágenes y videos locales

### Pesos encontrados y procedencia

Se revisaron el README, historial de `model/`, árbol, ramas, etiquetas, releases e issues
del [repositorio original](https://github.com/Hvora2005/industrial-defect-detection).
No se encontró una descarga pública de sus pesos entrenados. Su README propone entrenar
o colocar `model/best.pt`; **no se ejecutó entrenamiento**. Para obtener exactamente el modelo
de Hvora2005 hace falta que el autor publique o facilite ese checkpoint.

Para comprobar inferencia real se encontró una alternativa explícita:
[hazemaaa/steel-defect-yolo11n](https://huggingface.co/hazemaaa/steel-defect-yolo11n), publicada
por el autor de [SteelDefectDetection](https://github.com/hs29306060202959-ship-it/SteelDefectDetection).
Es YOLO11n entrenado para NEU-DET, **no el modelo de Hvora2005 ni un YOLO genérico COCO**.
Se verificaron sus seis clases y la arquitectura `yolo11n.yaml`. El checkpoint declara
entrenamiento de 150 épocas, tamaño 640 y semilla 42. Las métricas de su autor no se han
reproducido aquí ni se trasladan a piezas estampadas.

La licencia declarada para estos pesos es **AGPL-3.0**. Se conserva la licencia MIT del
repositorio original; los pesos externos no se incluyen en Git ni se renombran como `best.pt`.

El descargador verifica el SHA-256 antes de escribir y no reemplaza un archivo diferente:

```powershell
.\.venv\Scripts\python.exe tools/download_validation_model.py
```

Procedencia fijada: revisión `0d3d93d0ec8754d8dacc0585298fab32c4aea940`, archivo
`production/best.pt`, destino `model/steel-defect-yolo11n.pt`.
SHA-256: `621c742492ffe5137d214893499e47d59066685c53c400810de71cd26e4f8bac`.

El detector exige un checkpoint `.pt` existente con tarea `detect` y las seis clases NEU-DET.
Rechaza COCO, tareas distintas y YAML que construiría un modelo sin entrenar. No descarga
pesos automáticamente. La coincidencia de clases no acredita por sí sola procedencia o
precisión; por eso se documentan también la fuente y el hash.

### Reproducir la prueba con una imagen NEU-DET

Desde la raíz en PowerShell, descarga una muestra y su anotación del espejo que referencia
el conversor del repositorio original. No hace falta descargar el dataset completo:

```powershell
New-Item -ItemType Directory -Force outputs/validation | Out-Null
$sampleBase = 'https://raw.githubusercontent.com/siddhartamukherjee/NEU-DET-Steel-Surface-Defect-Detection/351bee21b56bbf97a1e1d18262bceb202eb7ef41'
Invoke-WebRequest "$sampleBase/IMAGES/patches_1.jpg" -OutFile outputs/validation/patches_1.jpg
Invoke-WebRequest "$sampleBase/ANNOTATIONS/patches_1.xml" -OutFile outputs/validation/patches_1.xml

.\.venv\Scripts\python.exe backend/capture.py --model model/steel-defect-yolo11n.pt --source outputs/validation/patches_1.jpg --imgsz 640 --grayscale --iou 0.6 --conf 0.4 --headless --output outputs/inference/patches_1.png --overwrite
```

La ficha de este modelo requiere entrada gris replicada en tres canales, `imgsz=640` y
NMS IoU `0.6`; los comandos lo indican expresamente. La conversión usa luminancia de Pillow,
como la implementación de su autor. Omite `--headless` para ver cajas, clases y confianza
en la ventana existente de OpenCV; la imagen espera una tecla. La consola imprime porcentajes
y las etiquetas dibujadas usan confianza de 0 a 1.

### Reproducir la prueba de video y cambiar el umbral

```powershell
.\.venv\Scripts\python.exe tools/create_test_media.py
.\.venv\Scripts\python.exe backend/capture.py --model model/steel-defect-yolo11n.pt --source outputs/demo/sample.avi --imgsz 640 --grayscale --iou 0.6 --conf 0.4 --headless --interval 0 --output outputs/inference/sample_annotated.avi --overwrite

# Prueba explícita de ausencia de detecciones al subir el umbral:
.\.venv\Scripts\python.exe backend/capture.py --model model/steel-defect-yolo11n.pt --source outputs/validation/patches_1.jpg --imgsz 640 --grayscale --iou 0.6 --conf 0.99 --headless --output outputs/inference/patches_high_threshold.png --overwrite
```

`--output` admite imagen para entrada de imagen y AVI/MJPG o MP4/mp4v para video/webcam.
Se comprobó AVI/MJPG; MP4 depende del codec disponible y no se validó en esta máquina.
Se conserva el FPS informado por la fuente; si no está disponible se usa 10 FPS. Se guarda
cada fotograma procesado; `--interval` afecta el tiempo de procesamiento, no el FPS guardado.
Se cierra el escritor al terminar, interrumpir o fallar. `--overwrite` autoriza reemplazar
la salida, pero nunca el archivo de entrada. Sin esa opción se rechaza una salida existente.

Sin `--model`, el cliente utiliza la API. Con `--model` ejecuta el mismo `DefectDetector`
localmente sin registrar en SQLite ni emitir al monitor. `--preview-only` sigue disponible
sin pesos; no permite guardar resultados fingiendo inferencia.

El comando original también sigue admitiendo una imagen, video o carpeta de imágenes y
ahora reutiliza el mismo detector, sin duplicar las reglas ni cargar un modelo por imagen:

```powershell
.\.venv\Scripts\python.exe training/test_inference.py --model model/steel-defect-yolo11n.pt --source outputs/validation --conf 0.4 --imgsz 640 --grayscale --iou 0.6 --out outputs/inference/legacy --overwrite
```

### Usar el modelo seleccionado en la API y el monitor existente

En una terminal de PowerShell, configura el modelo de terceros de forma explícita:

```powershell
$env:ACERO_MODEL_PATH = 'model/steel-defect-yolo11n.pt'
$env:ACERO_IMG_SIZE = '640'
$env:ACERO_GRAYSCALE = '1'
$env:ACERO_IOU = '0.6'
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

En otra terminal, abre [el monitor](http://127.0.0.1:8000/monitor) y ejecuta:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe backend/capture.py --source outputs/validation/patches_1.jpg --conf 0.4 --headless --output outputs/inference/api_patches.png --overwrite
.\.venv\Scripts\python.exe backend/capture.py --source outputs/validation/patches_1.jpg --conf 0.99 --headless
```

La API admite `POST /detect?conf=0.4` y `/upload?conf=0.4`, con `0 <= conf <= 1`;
los valores inválidos se rechazan. El teléfono conserva el valor predeterminado de `0.4`.
En modo API se guardan registros de prueba en SQLite y se difunden por WebSocket.
El JPEG del cliente puede producir pequeñas diferencias frente a inferencia local por
la recodificación de la imagen. Las variables `ACERO_*` solo afectan esa terminal y se
leen al arrancar; reinicia el servidor si cambias los pesos o su preprocesamiento.

La webcam mantiene las mismas opciones de selección, errores y captura. Cuando exista hardware:

```powershell
.\.venv\Scripts\python.exe backend/capture.py --camera 0 --model model/steel-defect-yolo11n.pt --imgsz 640 --grayscale --iou 0.6 --conf 0.4 --output outputs/inference/webcam.avi
```

### Interpretación y validación de la fase anterior de inferencia

- `FAIL` significa que el modelo detectó al menos un defecto; no es una decisión industrial
  validada de rechazo. Se conserva ese código para las detecciones existentes.
- `NO_DETECTIONS` significa que no hubo cajas por encima del umbral. **No significa PASS ni
  certifica que la pieza sea correcta**. Se muestra esa advertencia en consola, imagen y web.
- SQLite, estadísticas, tendencia, CSV y PDF distinguen ausencia de detecciones de defectos.
  Se conservan los registros históricos `PASS` como datos anteriores no verificados; ya no
  se generan automáticamente ni se cuentan los nuevos `NO_DETECTIONS` como fallos.
- La severidad sigue siendo la regla heurística original, no una evaluación industrial calibrada.

| Validación ejecutada con el modelo real | Resultado observado |
|---|---|
| Carga en Windows/CPU | Correcta; YOLO11n, seis clases NEU-DET y hash verificados |
| `patches_1.jpg`, confianza `0.4` | Tres detecciones `patches`: 87.50 %, 86.74 %, 78.39 %; PNG anotado guardado y revisado |
| Misma imagen, confianza `0.99` | `NO_DETECTIONS`; imagen con aviso guardada |
| PNG sintético | Sin detecciones; sin aprobación de pieza |
| AVI sintético de 30 fotogramas | 30 procesados y 30 recuperados del AVI de salida a 10 FPS |
| Contenido del AVI sintético | 5 fotogramas sin detecciones; 25 etiquetaron el círculo artificial como `scratches` (resultado espurio) |
| API con modelo real | `/health` listo; detección y ausencia de detecciones transmitidas al monitor y registradas por separado |
| Interfaz existente | Clases, confianza, imagen anotada y aviso de calidad no verificada comprobados en el navegador |
| Script de inferencia original adaptado | Carpeta de imágenes procesada correctamente con los mismos pesos |
| Suite automatizada ampliada | 88 pruebas aprobadas en Windows; una advertencia de obsolescencia de Starlette/HTTPX |

El video sintético prueba el recorrido de datos y también exhibe detecciones espurias; no
mide precisión. La muestra NEU-DET podría pertenecer al entrenamiento del modelo externo.
En esa fase no se evaluó un conjunto independiente, piezas estampadas ni hardware físico.
No se entrenó un modelo nuevo. Los dos registros de aquella comprobación de API permanecen
en la base local como inspecciones de prueba. La nueva fase añadió una captura manual del
video sintético: el historial de desarrollo contiene tres inspecciones de prueba.

## CUDA y cámara en tiempo real: fase actual

### Entorno verificado e instalación opcional de GPU

Se comprobó Windows 11 x64 y Python 3.14.3 con NVIDIA GeForce RTX 4050 Laptop GPU de 6 GB,
driver 610.78 y capacidad de cómputo 8.9. La instalación anterior era PyTorch `2.15.0+cpu`,
torchvision `0.29.2+cpu`, Ultralytics `8.4.210`; torchaudio no estaba instalado ni es necesario.

Se sustituyeron únicamente torch y torchvision por el par oficial `2.14.1+cu130` y
`0.29.1+cu130`, disponible para Python 3.14 y Windows. Ultralytics y las demás dependencias
se conservaron. `torch.cuda.is_available()` devolvió `True`, se comprobó un tensor CUDA y
se ejecutó el modelo real con `device=0`. **No se instaló CUDA Toolkit completo**.

El `13.3` de `nvidia-smi` corresponde al soporte del driver; el runtime de esta distribución
de PyTorch es `13.0`. No tienen que ser iguales. Referencias oficiales:
[versiones PyTorch para Windows/CUDA](https://pytorch.org/get-started/previous-versions/) y
[compatibilidad de drivers NVIDIA](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html).

Después de instalar las dependencias base, en PowerShell desde la raíz:

```powershell
# NVIDIA: wheels oficiales. La descarga de torch es de aproximadamente 2 GB.
.\.venv\Scripts\python.exe -m pip install --no-deps -r requirements-cuda.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import torch,torchvision; print(torch.__version__,torchvision.__version__); print(torch.version.cuda,torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

`--no-deps` evita cambiar dependencias ajenas en el entorno base ya instalado. Para un equipo
sin NVIDIA, conserva la instalación CPU o instala el mismo par desde el índice CPU:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-deps torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip check
```

La aplicación acepta `auto`, `cpu` y `cuda`. `auto` selecciona CUDA si está disponible; si
no, avisa y usa CPU. Una solicitud explícita `cuda` genera error cuando no está disponible,
sin cambiar silenciosamente a CPU. Un error de ejecución GPU tampoco se oculta con un cambio
de dispositivo. Se puede detener la captura y seleccionar CPU desde la web.

### Ejecutar backend y controles del dashboard

Se utilizan exactamente los mismos pesos ya validados, con el mismo hash y preprocesamiento:

```powershell
$env:ACERO_MODEL_PATH = 'model/steel-defect-yolo11n.pt'
$env:ACERO_IMG_SIZE = '640'
$env:ACERO_GRAYSCALE = '1'
$env:ACERO_IOU = '0.6'
$env:ACERO_DEVICE = 'auto'
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Abre [Dashboard](http://127.0.0.1:8000/dashboard). El equipo sin GPU puede usar los mismos
comandos con `ACERO_DEVICE='cpu'`. El frontend usa fuentes del sistema, sin peticiones a
Google Fonts ni dependencias CDN. Una vez instalados paquetes y pesos, la captura e
inferencia funcionan localmente. Las descargas y enlaces de documentación sí necesitan red.

1. Pulsa **Buscar cámaras** con la captura detenida. El índice puede corresponder a una
   cámara integrada o USB; OpenCV no proporciona aquí un nombre estable del hardware.
   Si `Auto` falla, selecciona `DirectShow` o `Media Foundation` y vuelve a buscar.
2. Elige la fuente, ancho, alto, FPS solicitados, confianza y `Auto`, `GPU CUDA` o `CPU`.
   La web muestra resolución real de los fotogramas y FPS informados por el controlador;
   la cámara puede ignorar los valores solicitados. Los ajustes de cámara no redimensionan
   archivos de video: estos mantienen sus dimensiones/FPS originales.
3. Pulsa **Iniciar inspección**. La vista previa dibuja cajas, clases y confianza, muestra
   CPU/GPU, latencia YOLO y FPS de procesamiento. **No guarda inspecciones por fotograma**.
4. Coloca una pieza y pulsa **Capturar e inspeccionar una pieza** una sola vez. Ese evento
   guarda un registro en SQLite y dos JPEG, original y anotado, en `outputs/captures/`.
   Los enlaces permiten descargarlos; el monitor existente recibe la inspección por WebSocket.
5. Para ajustar el umbral durante la captura, cambia **Confianza** y pulsa **Aplicar confianza**.
   La web confirma el valor recibido por el backend.
6. Pulsa **Detener** para liberar la fuente. Puedes cambiar cámara, resolución o dispositivo
   y volver a iniciar sin reiniciar FastAPI. Recargar la página recupera la sesión activa.

Los contadores representan **eventos de inspección controlados por el operador**, no objetos
físicos únicos reconocidos automáticamente. Pulsar otra vez para la misma pieza representa
otra inspección. Reintentos de red con el mismo UUID reutilizan el resultado (últimos 64
eventos en memoria); los archivos existentes tampoco se sobrescriben tras reiniciar. No hay
sensor, seguimiento de identidad de piezas, banda, ESP32 ni mecanismo de rechazo.

Si la cámara se desconecta, está ocupada o deja de leer, se muestra el error y se libera
la captura. Reconecta y vuelve a iniciar; no hay reconexión automática. Un controlador que
quede bloqueado en una lectura puede impedir una parada inmediata: el servidor informa
la situación en lugar de afirmar que ya se detuvo. No se verificó desconexión física.

### Prueba con video sin cámara y uso por consola

La fuente **Demo: sample.avi** repite el video sintético para probar controles, capturas y
registro manual sin hardware. Se puede cambiar el archivo de demostración al arrancar
mediante `ACERO_DEMO_VIDEO`, ruta local relativa a la raíz o absoluta.

```powershell
.\.venv\Scripts\python.exe tools/create_test_media.py
# Inferencia real CUDA de la imagen NEU-DET:
.\.venv\Scripts\python.exe backend/capture.py --model model/steel-defect-yolo11n.pt --source outputs/validation/patches_1.jpg --imgsz 640 --grayscale --iou 0.6 --device cuda --conf 0.4 --headless --output outputs/inference/patches_gpu.png --overwrite
# Webcam local; q/Escape detiene y libera. No registra piezas por fotograma.
.\.venv\Scripts\python.exe backend/capture.py --camera 0 --backend dshow --width 640 --height 480 --fps 30 --model model/steel-defect-yolo11n.pt --imgsz 640 --grayscale --iou 0.6 --device auto --conf 0.4
```

La consola informa configuración solicitada/efectiva, dispositivo y rendimiento. El argumento
`--device` también se admite en `training/test_inference.py`. En la API, `/detect`, `/upload`
y `/preview` aceptan `?device=auto|cpu|cuda`; la selección explícita prevalece sobre el valor
predeterminado `ACERO_DEVICE`. El modo periódico del teléfono ahora utiliza `/preview` sin
incrementar contadores; su botón manual sigue registrando una inspección.

### Rendimiento medido, no estimado a partir de especificaciones

```powershell
.\.venv\Scripts\python.exe tools/benchmark_inference.py --model model/steel-defect-yolo11n.pt --image outputs/validation/patches_1.jpg --imgsz 640 --conf 0.4 --iou 0.6 --warmup 5 --runs 30
```

Medición sin pruebas automatizadas simultáneas: mismos pesos, imagen, entrada gris de 640 px,
confianza `0.4`, IoU `0.6` y parámetros FP32. Cinco calentamientos excluidos y 30 muestras por
dispositivo, sincronizando CUDA antes/después de medir. Carga de pesos, captura, HTTP y
calentamiento están fuera de las muestras. `outputs/benchmark/cpu_gpu.json` conserva muestras,
hash, versiones, dispositivo real de parámetros y estadísticas:

| Dispositivo | YOLO media / mediana | FPS aprox. YOLO | Con anotación/JPEG media / mediana | FPS aprox. con anotación/JPEG |
|---|---|---|---|---|
| CPU | 41.683 / 39.151 ms | 23.99 | 43.173 / 40.660 ms | 23.16 |
| RTX 4050 (`cuda:0`) | 11.410 / 10.392 ms | 87.64 | 12.991 / 12.032 ms | 76.98 |

YOLO incluye preparación de entrada, red y NMS; el segundo tiempo añade dibujo y codificación.
Los FPS son `1000 / latencia media`, no la velocidad garantizada de una línea ni los FPS de
la webcam. En la web, los FPS de procesamiento incluyen lectura, inferencia y codificación,
excluyen la espera deliberada entre fotogramas y se suavizan con hasta 30 muestras. El inicio
incluye calentamiento y puede mostrar valores bajos; temperatura, carga y alimentación alteran
las mediciones. El video demo sigue siendo de 10 FPS aunque la capacidad de cálculo sea mayor.

### Validaciones realizadas y límites

- PyTorch CUDA, tensor en GPU, arquitectura/clases, inferencia `device=0` y parámetros
  `cuda:0`/FP32 comprobados. La imagen real produjo tres detecciones `patches`, aproximadamente
  87.49 %, 86.74 % y 78.38 % en GPU; las pequeñas diferencias numéricas no son una evaluación de precisión.
- Cámara física **HD Webcam**, índice 0 y DirectShow: lectura e inferencia CUDA comprobadas
  a 640×480, aproximadamente 30 FPS informados; cierre y liberación probados en CLI y backend.
  No se determinó si es integrada o una USB externa; no se afirma haber validado una webcam
  externa concreta ni su desconexión física.
- Vista previa física dejó el historial en 2 registros. En la web, el video demo incrementó
  el historial de 2 a 3 solo al pulsar captura. Un reenvío del mismo UUID mantuvo 3 registros;
  ambos JPEG se guardaron y se pudieron decodificar.
- Buscar, iniciar, detener, cambiar CUDA↔CPU sin reiniciar, aplicar confianza `0.99` y recuperar
  la vista previa tras recargar la web comprobados. El servidor de prueba se detiene al finalizar.
- **108 pruebas automatizadas aprobadas**, una advertencia de Starlette/HTTPX ya existente;
  `pip check` y comprobaciones de sintaxis JavaScript correctas. Los mocks cubren ausencia de
  CUDA, petición explícita de GPU, cámaras ocupadas/desconectadas y reintentos simultáneos.
- Siguen pendientes precisión sobre piezas estampadas, iluminación/posición reales, webcam
  USB externa identificada, desconexión física y teléfono físico. El modelo no se cambió ni entrenó.
  La ausencia de detecciones continúa siendo calidad no verificada. La demo puede producir
  detecciones espurias sobre figuras sintéticas.

Archivos de esta fase: `backend/runtime.py`, `backend/camera.py`, `backend/detector.py`,
`backend/capture.py`, `backend/config.py`, `backend/main.py`; `frontend/camera.js`,
`frontend/dashboard.html`, `frontend/index.html`, `frontend/app.js`, `frontend/monitor.html`,
`frontend/monitor.js`, `frontend/style.css`; `training/test_inference.py`,
`tools/benchmark_inference.py`, `requirements-cuda.txt`, `README.md`; pruebas
`test_runtime.py`, `test_camera_session.py`, `test_benchmark.py`, `test_api.py`,
`test_local_inference.py` y `test_frontend_results.py`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_capture.py -q
```

Las pruebas generan y decodifican imágenes/videos reales en carpetas temporales y simulan
cámaras ausentes, desconexiones, selección, errores HTTP y cierre de recursos. La integración
comprueba el multipart contra FastAPI, los endpoints originales, SQLite temporal y WebSocket
con un detector simulado. **No valida inferencia YOLO ni hardware**.
La suite amplía las 50 pruebas iniciales con contratos del detector, umbrales, rechazo de
modelos incompatibles, guardado y lectura de video, errores de codec, descarga con hash,
estadísticas, reportes y presentación de estados. Las tres pruebas de renderizado usan
Node si está instalado y se omiten si no lo está; no es una dependencia de ejecución.
Las validaciones con pesos reales de la tabla anterior se ejecutan aparte de pytest.

El archivo original `training/test_inference.py` es un script manual, no una suite automatizada.
Requiere pesos y muestras reales para producir resultados:

```powershell
.\.venv\Scripts\python.exe training/test_inference.py --model model/best.pt --source "C:\ruta\imagenes" --conf 0.4
```

### Validación anterior: fase de captura

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

En aquella fase de captura no se entrenó ni descargó ningún modelo. La inferencia posterior
usa pesos públicos ya entrenados de otro autor. La validación actual de cámara y CUDA se
documenta arriba; la captura de teléfono físico sigue pendiente.

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
| `/preview` | POST | Inferencia de fotogramas sin registrar inspecciones |
| `/runtime` | GET | Versiones, disponibilidad CUDA y GPU detectada |
| `/cameras` | GET | Buscar índices OpenCV con la fuente detenida |
| `/camera/start`, `/camera/stop` | POST | Iniciar/detener fuente sin reiniciar FastAPI |
| `/camera/status`, `/camera/stream` | GET | Estado, rendimiento y vista previa MJPEG |
| `/camera/settings` | POST | Aplicar `conf` durante la captura |
| `/camera/capture` | POST | Captura manual: JSON `request_id` UUID; original/anotada y un registro |
| `/captures/{filename}` | GET | Descargar JPEG de una captura manual |

## Créditos y licencia

Proyecto original de **Hemin Vora**. Adaptación universitaria **Acero Cifrado**.
Se conserva la [licencia MIT](LICENSE).
