# Datos publicos de El Salvador

## Censo 2024

- Dataset: `censo_2024_poblacion_nombres.csv`
- Fuente oficial: Banco Central de Reserva de El Salvador, servicio ArcGIS `tabla_poblacion`, tabla `Tabla de Poblacion (Ultima)`.
- REST: `https://services8.arcgis.com/xSn1Pefr3M9zkw7Z/arcgis/rest/services/tabla_poblacion/FeatureServer/0/query`
- Fecha de descarga: 2026-09-22.
- Grano: ano censal, departamento, municipio, distrito, nivel geografico, rango de edad y genero.
- `nivel_geografico` distingue `nacional`, `departamento`, `municipio` y `distrito`. Para preguntas de departamentos se debe filtrar `nivel_geografico = 'departamento'`; no se deben sumar todos los niveles.
- `departamento_nombre`, `municipio_nombre` y `distrito_nombre` provienen de los servicios oficiales `Selector_departamentos`, `Selector_municipio` y `Selector_distrito` del Geoportal BCR.
- La columna `poblacion` usa el campo absoluto `Pob`; no se usa el campo firmado empleado para graficos de piramide.
- Se descargaron 12,880 registros mediante paginacion ArcGIS. La fuente publica incluye el agregado nacional (`00/0000/000000`) y registros con el codigo `15` a nivel distrital sin fila departamental; esos registros no se mezclan al calcular totales departamentales.

## Remesas

- Dataset: `bcr_remesas_mensuales.csv`
- Fuente oficial: `https://estadisticas.bcr.gob.sv/serie/ingresos-mensuales-de-remesas-familiares?lang=es`.
- Fecha de consulta: 2026-09-22.
- Cobertura publicada en la pagina: julio de 2025 a julio de 2026.
- Unidad: millones de US$. Los valores estan marcados como preliminares por la fuente.

## IPC

- Dataset: `bcr_ipc_indice.csv`
- Fuente oficial: `https://estadisticas.bcr.gob.sv/serie/indice-de-precios-al-consumidor-ipc?lang=es`.
- Fecha de consulta: 2026-09-22.
- Cobertura publicada en la pagina: noviembre de 2024 a agosto de 2026.
- Base: diciembre de 2009 igual a 100.

## Clima MARN/SNET

- Dataset: `marn_clima_indicadores_2025.csv`
- Informe oficial: `https://srt.snet.gob.sv/app_documentos/documentos_area/clima/resumen_climatologico_anual/resumen_2025_actual.pdf`
- Pagina de referencia: `https://www.snet.gob.sv/ver/meteorologia/clima/resumen+climatologico+anual/`
- Fecha de descarga: 2026-09-22.
- Cobertura: indicadores explicitos del Boletin Climatologico Anual 2025, incluyendo lluvia, temperaturas, evento de lluvias, sequia y ola de calor.
- Grano: indicador por estacion, departamento y periodo cuando el informe publica esos datos.
- Limitacion: el PDF contiene mapas e interpretacion, no una serie diaria completa. El CSV solo transcribe valores numericos explicitos del informe y no representa toda la red de estaciones.
- Licencia y uso: el MARN permite la reproduccion total o parcial, solicitando consignar la fuente y el periodo de validez.

## Limitacion

La base censal individual CSV/SPSS requiere completar el formulario de descarga del BCR. No se incorpora porque no es un dataset agregado y puede contener datos que requieren revisión de autorización, anonimización y uso. Este lote usa únicamente tablas públicas agregadas.
