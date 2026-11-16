# Zona

El destino para elegir o soltar archivos en la columna lateral: borde punteado claro, ícono `subir`, título y límites.

## Estados

- Reposo: borde 1.5px punteado en `nieve` al 32%, `radio-14`, ícono `niebla`.
- Hover o `.arrastrando`: borde `resaltador` y velo `resaltador-velo`; el ícono sube 3px y se pinta de `resaltador`.
- Foco: el input oculto (`.archivo-oculto`) pasa el anillo `resaltador` a la zona.

## Qué provee quien lo usa

Un `<input type="file" class="archivo-oculto">` seguido de su `<label class="zona">`, con los tipos aceptados y los límites dichos en la zona ("Hasta cinco, de 10 MB como máximo cada uno."). Al arrastrar sobre toda la página, el chat entero se ofrece como destino ("Soltá los archivos para preguntarles").
