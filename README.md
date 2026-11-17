# KFall Labeler

Interfaz grafica PyQt6/pyqtgraph para etiquetar manualmente las grabaciones de
KFall con las actividades de UCI HAR y las etiquetas adicionales Subiendo y Bajando.

```text
kfall_labeler/
├── label_kfall_manual.py   # lanzador (linea de comandos)
├── gui.py                  # ventana PyQt6/pyqtgraph
├── editor.py               # modelo de etiquetas y guardado seguro del JSON
├── tasks.py                # descripciones y videos de referencia de las tareas KFall
├── requirements.txt        # dependencias de la GUI
├── dataset/                # copia local de KFall (ver dataset/README.md)
└── tests/                  # pruebas del modelo y de la interfaz
```

La herramienta reutiliza los cargadores del repositorio (`loaders/`,
`preprocess/`, `labeling/kfall_manual_labels.py`), por eso debe quedar dentro
de la raiz de `Neuromorphic-HAR`.

## Instalacion

```bash
python -m venv .venv
.venv/bin/python -m pip install -r kfall_labeler/requirements.txt
```

Despues descarga KFall siguiendo [`dataset/README.md`](dataset/README.md).

## Uso

Desde la raiz del repositorio:

```bash
.venv/bin/python kfall_labeler/label_kfall_manual.py
# equivalente:
.venv/bin/python -m kfall_labeler
```

Por defecto se abre `kfall_labeler/dataset/KFall`. Si no existe, se usa
`data/KFall`. Las etiquetas se guardan en `annotations/kfall_manual_labels.json`,
que `train_kfall.py` usa automaticamente.

| Opcion | Uso |
|---|---|
| `--dataset-root PATH` | Carpeta KFall con `sensor_data/` y `label_data/`. |
| `--label-dir PATH` | Carpeta alternativa de los XLSX oficiales. |
| `--output PATH` | Otro JSON de etiquetas (`--annotation-file PATH` al entrenar). |
| `--exclude-tasks T05 ...` | Tareas ocultas; sin valores muestra todas. |
| `--save-frame PNG` | Exporta una captura sin abrir la ventana y termina. |

Por defecto se muestran todas las tareas disponibles (T01-T36), incluidas
T05, T13-T16 y T18-T19. Esto no cambia las exclusiones del entrenamiento.
Para ocultar tareas de forma explicita:

```bash
.venv/bin/python kfall_labeler/label_kfall_manual.py --exclude-tasks T05 T13 T14 T15 T16 T18 T19
```

Las exclusiones solo ocultan grabaciones; sus etiquetas existentes se conservan.

## Interfaz

![Captura de pantalla de KFall Labeler](assets/kfall-labeler.png)

- **Izquierda:** filtros por sujeto y por estado (todas o solo pendientes), y la
  lista de grabaciones con la descripcion de su tarea KFall en español.
  La descripcion completa tambien aparece sobre los graficos y como ayuda al
  pasar el cursor sobre la grabacion. Cada grabacion se marca como UCI HAR (●), antigua
  Dynamic/Static (◐) o pendiente (○).
- **Derecha:** graficos X, Y y Z sincronizados mas una linea de etiquetas. El
  selector cambia entre acelerometro (g) y giroscopio (deg/s).
- **Actividad:** muestra el nombre de la etiqueta en la ventana seleccionada;
  el boton abre el video de referencia de la tarea cuando hay un enlace directo
  disponible y, en los demas casos, las referencias oficiales de KFall.
  Las descripciones y los enlaces proceden de la
  [tabla oficial de tareas y videos](https://docs.google.com/spreadsheets/d/1bkMwB1e_gjYQm-7r2Ago73zv9xzDxeR3lg7WO0toO0E/).
  T03 solo tiene un nombre de archivo en esa tabla, por lo que abre el sitio oficial.
- **Ventana temporal:** arrastra sobre la senal para crearla. Arrastra su
  interior para moverla y sus bordes para cambiar su duracion. Tambien puedes
  ajustar inicio y fin con los campos numericos.
- **Vista:** rueda para zoom, Ctrl+arrastre para desplazarte, **Zoom ventana** y
  **Ver todo**.

| Tecla | Accion |
|---|---|
| `1` | Caminando |
| `2` | Subiendo escaleras |
| `3` | Bajando escaleras |
| `4` | Sentado |
| `5` | De pie |
| `6` | Acostado |
| `7` | Subiendo |
| `8` | Bajando |
| `Supr` | Borrar la etiqueta de la seleccion |
| `Ctrl+Z` | Deshacer |
| `Ctrl+S` | Guardar como revisada |

Los intervalos Fall y PostImpact salen de los XLSX oficiales, con las mismas
reglas del entrenamiento, y no se pueden modificar. Las muestras normales sin
etiqueta empiezan sin asignar.

## Formato guardado y entrenamiento

Cada grabacion guarda:

- `activity_intervals`: `[frame_inicio, frame_fin_exclusivo, actividad]`, con
  los identificadores UCI HAR originales (0-5) y dos extensiones:
  `6=ASCENDING` (Subiendo) y `7=DESCENDING` (Bajando), independientes de las
  actividades de escaleras. Los nombres internos se conservan en ingles;
  los botones, sus ayudas y las etiquetas visibles se muestran en español.
- `intervals`: la equivalencia usada por el entrenamiento actual de KFall. Las
  tres actividades de caminar, Subiendo y Bajando son `Dynamic=1`;
  Sentado, De pie y Acostado son `Static=2`.

El esquema ampliado se identifica como `uci_har_extended`; las etiquetas
guardadas con el esquema anterior siguen siendo compatibles.

Las etiquetas antiguas Dynamic/Static se muestran como "antiguas" y siguen en
el filtro de pendientes hasta reetiquetarlas con UCI HAR y guardarlas.

El guardado es atomico. Si solo existe `kfall_manual_labels.json.bak`, se carga
y no se modifica; en cada guardado la version anterior queda en `.json.previous`.
El editor no sobrescribe un archivo modificado por fuera, pide confirmacion
ante cambios sin guardar y avisa si una grabacion queda etiquetada solo en
parte. Los extremos sin etiqueta se excluyen del entrenamiento.

Usa el editor sobre los sujetos de entrenamiento. No corrijas etiquetas de
validacion o test a partir de las predicciones del modelo.

## Pruebas

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s kfall_labeler/tests -v
```
