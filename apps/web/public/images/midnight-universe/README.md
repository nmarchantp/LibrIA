# Recurso de Biblioteca de Medianoche

`moonlit-library-v1.webp` utiliza directamente la segunda imagen adjunta por el usuario: biblioteca nocturna con luna, castillo, libro, esfera armilar, pluma y faroles. No se generó una variante ni se incluyeron textos de la captura de interfaz.

El PNG recibido de 1672 × 941 px permanece en `artifacts/midnight-universe-sources/moonlit-library-v1.png`. Se codificó a WebP con calidad 0,86: 314 550 bytes, aproximadamente 307 KiB, conservando dimensiones y composición.

`MidnightInterior.css` reutiliza la misma descarga con encuadres diferentes:

- Fondo continuo del mural: escena centrada antes de Tu rincón, desde arriba hasta las pestañas. Veladura lateral e inferior para legibilidad.
- Sidebar: recorte visual del lado izquierdo de la imagen, con máscara que desvanece el perímetro.
- Tu rincón: lado izquierdo reflejado mediante CSS para situar el farol hacia la derecha, sin reflejar el texto del panel.
- Perfil: banner automático con la escena original.

Los recortes, el reflejo y las máscaras son estilos CSS; el archivo de imagen permanece sin esos cambios. Las ilustraciones no reciben animaciones ni capturan clics.
