import streamlit as st
import os
import sys
import urllib.parse
from pathlib import Path
import tempfile
import zipfile
import io
from datetime import datetime
from yt_dlp import YoutubeDL

# -----------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------
st.set_page_config(
    page_title="Download Music 2 MP3",
    page_icon="🎵",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------
# CLASE PRINCIPAL ADAPTADA A STREAMLIT
# -----------------------------------------------------------
class DownloadMusic2MP3Web:
    def __init__(self):
        # En Streamlit Cloud el directorio es de solo lectura,
        # usamos /tmp para escribir archivos temporales.
        self.base_dir = Path(tempfile.gettempdir()) / "download_music_web"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.output_dir = self.base_dir / "Canciones_descargadas"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.faltantes_file = self.base_dir / "Canciones faltantes.txt"

    # -------------------------------------------------------
    # VALIDACIÓN DE ENLACES
    # -------------------------------------------------------
    @staticmethod
    def es_enlace_youtube(url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc.lower() in [
                "www.youtube.com",
                "youtube.com",
                "youtu.be",
                "m.youtube.com",
                "music.youtube.com",
            ]
        except Exception:
            return False

    # -------------------------------------------------------
    # DESCARGA INDIVIDUAL
    # -------------------------------------------------------
    def descargar_audio(self, url: str, progress_callback=None):
        """
        Descarga el audio en M4A/AAC sin usar FFmpeg.
        Devuelve (ok: bool, mensaje: str, archivo: Path | None)
        """
        if not self.es_enlace_youtube(url):
            self._registrar_faltante(url)
            return False, "El enlace no corresponde a un video de YouTube.", None

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(self.output_dir / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_callback] if progress_callback else [],
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                archivo = Path(ydl.prepare_filename(info))

            return (
                True,
                f"✅ '{info.get('title', 'audio')}' descargado correctamente.",
                archivo,
            )

        except Exception as e:
            self._registrar_faltante(url)
            return False, f"❌ Error al descargar: {e}", None

    # -------------------------------------------------------
    # REGISTRO DE FALLOS
    # -------------------------------------------------------
    def _registrar_faltante(self, url: str):
        with open(self.faltantes_file, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")

    # -------------------------------------------------------
    # EMPAQUETAR RESULTADOS EN ZIP
    # -------------------------------------------------------
    def crear_zip(self, archivos):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for archivo in archivos:
                if archivo and archivo.exists():
                    zf.write(archivo, arcname=archivo.name)
        buffer.seek(0)
        return buffer


# -----------------------------------------------------------
# INSTANCIA ÚNICA
# -----------------------------------------------------------
@st.cache_resource
def get_downloader():
    return DownloadMusic2MP3Web()


downloader = get_downloader()

# -----------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------
st.title("🎵 Download Music 2 MP3")
st.caption("Descarga audio de YouTube en formato M4A/AAC directamente desde tu navegador.")

# GIF opcional (si existe en la carpeta local del repo)
gif_path = Path("Gifs/musica-escuchando.gif")
if gif_path.exists():
    st.image(str(gif_path), use_container_width=True)

# Tabs: enlace individual / archivo txt
tab1, tab2 = st.tabs(["🔗 Descargar con link", "📄 Descargar desde archivo TXT"])

# -----------------------------------------------------------
# TAB 1 — DESCARGA INDIVIDUAL
# -----------------------------------------------------------
with tab1:
    st.subheader("Descargar una canción")
    url = st.text_input(
        "Link del video de YouTube",
        placeholder="https://www.youtube.com/watch?v=...",
    )

    if st.button("⬇️ Descargar audio M4A", type="primary", use_container_width=True):
        if not url.strip():
            st.warning("Por favor ingresa un enlace válido.")
        else:
            progress_bar = st.progress(0, text="Iniciando descarga...")
            status_text = st.empty()

            def hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        progress_bar.progress(pct, text=f"Descargando... {pct}%")
                elif d["status"] == "finished":
                    progress_bar.progress(100, text="Procesando archivo...")

            with st.spinner("Descargando..."):
                ok, mensaje, archivo = downloader.descargar_audio(url.strip(), hook)

            if ok:
                progress_bar.progress(100, text="¡Completado!")
                st.success(mensaje)
                if archivo and archivo.exists():
                    with open(archivo, "rb") as f:
                        st.download_button(
                            label="💾 Guardar archivo",
                            data=f,
                            file_name=archivo.name,
                            mime="audio/mp4",
                            use_container_width=True,
                        )
            else:
                progress_bar.empty()
                st.error(mensaje)

# -----------------------------------------------------------
# TAB 2 — DESCARGA MASIVA DESDE TXT
# -----------------------------------------------------------
with tab2:
    st.subheader("Descargar varias canciones desde un archivo .txt")
    st.info(
        "📌 Los enlaces deben estar **sin comillas** y **uno por línea**.\n\n"
        "Ejemplo:\n```\nhttps://www.youtube.com/watch?v=abc123\n"
        "https://youtu.be/def456\n```"
    )

    archivo_txt = st.file_uploader("Selecciona tu archivo .txt", type=["txt"])

    if archivo_txt is not None:
        contenido = archivo_txt.read().decode("utf-8", errors="ignore")
        links = [l.strip() for l in contenido.splitlines() if l.strip()]

        st.write(f"🔗 **{len(links)} enlaces detectados:**")
        with st.expander("Ver enlaces"):
            for i, l in enumerate(links, 1):
                st.write(f"{i}. {l}")

        if st.button("⬇️ Descargar todos", type="primary", use_container_width=True):
            if not links:
                st.warning("El archivo está vacío o no contiene enlaces válidos.")
            else:
                progreso = st.progress(0, text="Iniciando descargas...")
                estado = st.empty()
                resultados = []
                archivos_descargados = []

                for i, link in enumerate(links, 1):
                    estado.info(f"🎧 Procesando {i}/{len(links)}: {link}")
                    ok, mensaje, archivo = downloader.descargar_audio(link)
                    resultados.append((link, ok, mensaje))
                    if ok and archivo:
                        archivos_descargados.append(archivo)

                    progreso.progress(
                        int(i / len(links) * 100),
                        text=f"Completado {i}/{len(links)}",
                    )

                estado.success(f"✅ Proceso finalizado. {len(archivos_descargados)} descargadas.")

                # Resumen
                with st.expander("📋 Ver resultados detallados", expanded=True):
                    for link, ok, msg in resultados:
                        if ok:
                            st.success(msg)
                        else:
                            st.error(f"{msg} → {link}")

                # ZIP con todo
                if archivos_descargados:
                    zip_buffer = downloader.crear_zip(archivos_descargados)
                    st.download_button(
                        label=f"📦 Descargar todas ({len(archivos_descargados)}) en ZIP",
                        data=zip_buffer,
                        file_name=f"canciones_{datetime.now():%Y%m%d_%H%M%S}.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

# -----------------------------------------------------------
# SIDEBAR — INFO
# -----------------------------------------------------------
with st.sidebar:
    st.header("ℹ️ Información")
    st.markdown(
        """
        **Descarga audio de YouTube en M4A/AAC** sin necesidad de FFmpeg.

        - ✅ Sin conversiones pesadas
        - ✅ Compatible con Windows, Linux y macOS
        - ✅ Multi-descarga desde TXT
        - ✅ Empaquetado automático en ZIP

        ⚠️ Respeta los derechos de autor y los términos de YouTube.
        """
    )

    if st.button("🗑️ Limpiar caché"):
        st.cache_resource.clear()
        st.success("Caché limpiada.")
        st.rerun()
