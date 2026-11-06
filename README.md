# ClipMaster AI

Aplicación web independiente para convertir videos largos en clips verticales.

## Requisitos
- Python 3.10+
- FFmpeg y FFprobe instalados y disponibles en PATH
- Para subtítulos automáticos: instalar `faster-whisper` (descarga un modelo abierto la primera vez).

## Ejecutar localmente

### Windows
1. Instala FFmpeg y agrega `ffmpeg` y `ffprobe` al PATH.
2. Instala Python 3.10 o superior.
3. Abre una terminal en esta carpeta y ejecuta:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Abre http://127.0.0.1:8000

## Ejecutar con Docker
Con Docker instalado:
```bash
docker compose up --build
```
Abre http://localhost:8000

## Sobre la IA y los costos
- La transcodificación usa FFmpeg, software gratuito.
- Los subtítulos usan faster-whisper, un modelo abierto que se ejecuta localmente. La primera ejecución descarga el modelo y puede consumir bastante RAM/CPU.
- Si faster-whisper no está instalado, se crean clips sin subtítulos.
- No requiere ElevenLabs ni claves de API pagas.

## Estado de esta primera versión
Incluye carga de archivos, creación de clips, recorte vertical y subtítulos locales opcionales. La selección de clips es básica: distribuye segmentos a lo largo del video y, si hay transcripción, prioriza ventanas con más palabras. No equivale todavía al análisis semántico y de viralidad de Opus Clip.

## Próximas mejoras recomendadas
1. Detección semántica de momentos destacados.
2. Seguimiento de rostro y encuadre inteligente.
3. Editor para ajustar inicio/final y subtítulos.
4. Plantillas de subtítulos animados.
5. Cola de trabajos y progreso en tiempo real.
6. Autenticación, límites de subida y almacenamiento seguro para despliegue público.

## Seguridad antes de publicarla
Esta es una base de desarrollo. Antes de exponerla a Internet hay que añadir autenticación, límites de tamaño/duración, control de concurrencia, limpieza automática de archivos, protección contra abuso y almacenamiento privado.
