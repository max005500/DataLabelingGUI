# Dataset KFall para el etiquetador

Esta carpeta guarda la copia local de KFall que abre la GUI. Los datos **no**
se versionan en Git; solo este README.

## 1. Solicitar acceso

KFall no se descarga de forma anonima. Su licencia prohibe redistribuirlo, asi
que no uses copias de terceros, por ejemplo de Kaggle.

1. Abre el sitio oficial: <https://sites.google.com/view/kfalldataset>.
2. Completa el formulario de solicitud al final de la pagina con tu nombre,
   correo institucional, afiliacion y uso previsto.
3. El equipo de KFall verifica tu identidad y afiliacion y te responde por
   correo. Tras la aprobacion se habilita el boton de descarga en el mismo sitio.

## 2. Descargar

Descarga los dos archivos:

| Archivo | Contenido |
|---|---|
| `sensor_data.zip` | 32 carpetas por sujeto (`SA06`, `SA07`...) con un CSV por intento (`SA06T01R01.csv`: sujeto 06, tarea 01, intento 01). |
| `label_data.zip` | 32 libros `SAxx_label.xlsx` con `Fall_onset_frame` y `Fall_impact_frame` de cada caida. |

## 3. Descomprimir aqui

Desde la raiz del repositorio:

```bash
mkdir -p kfall_labeler/dataset/KFall
unzip ~/Descargas/sensor_data.zip -d kfall_labeler/dataset/KFall
unzip ~/Descargas/label_data.zip  -d kfall_labeler/dataset/KFall
```

La estructura final debe ser:

```text
kfall_labeler/dataset/
├── README.md
└── KFall/
    ├── sensor_data/
    │   ├── SA06/
    │   │   ├── SA06T01R01.csv   (tambien se acepta S06T01R01.csv)
    │   │   └── ...
    │   └── ...
    └── label_data/
        ├── SA06_label.xlsx
        └── ...
```

Si el zip crea una carpeta intermedia, por ejemplo `KFall/sensor_data/sensor_data/`,
mueve su contenido un nivel arriba.

### Si ya tienes KFall en `data/KFall`

No hace falta duplicarlo. La GUI usa `data/KFall` automaticamente cuando esta
carpeta no existe, o puedes enlazarlo:

```bash
ln -s ../../data/KFall kfall_labeler/dataset/KFall
```

## 4. Verificar

```bash
ls kfall_labeler/dataset/KFall/sensor_data | wc -l   # 32 sujetos
ls kfall_labeler/dataset/KFall/label_data  | wc -l   # 32 xlsx
python kfall_labeler/label_kfall_manual.py --save-frame results/kfall_label_editor.png
```

El ultimo comando abre el dataset sin interfaz visible y exporta una captura;
si falla, el mensaje indica la ruta o el archivo con problemas.

## Cita

Yu, X., Jang, J., & Xiong, S. (2021). *A Large-Scale Open Motion Dataset (KFall)
and Benchmark Algorithms for Detecting Pre-impact Fall of the Elderly Using
Wearable Inertial Sensors*. Frontiers in Aging Neuroscience, 13, 692865.
<https://doi.org/10.3389/fnagi.2021.692865>
