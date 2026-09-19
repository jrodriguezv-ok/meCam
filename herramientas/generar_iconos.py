"""
Genera servidor/iconos.py con los íconos de MeCam (Phosphor Icons, licencia MIT).

Uso:
    npm install @phosphor-icons/core
    python herramientas/generar_iconos.py ruta/a/node_modules/@phosphor-icons/core
Los íconos quedan incrustados en el programa, así el centro de control funciona sin internet.
"""
import os
import re
import sys

# clave usada en las páginas -> (nombre en Phosphor, peso)
ICONOS = {
    "logo": ("video-camera", "duotone"),
    "camara": ("camera", "duotone"),
    "ampliar": ("arrows-out", "bold"),
    "reducir": ("arrows-in", "bold"),
    "cerrar": ("x", "bold"),
    "mas": ("magnifying-glass-plus", "duotone"),
    "menos": ("magnifying-glass-minus", "duotone"),
    "reset": ("arrow-counter-clockwise", "bold"),
    "campana": ("bell-ringing", "duotone"),
    "campana_off": ("bell-slash", "duotone"),
    "recuadro": ("selection-slash", "duotone"),
    "actividad": ("pulse", "duotone"),
    "pulse": ("pulse", "bold"),
    "grabaciones": ("film-strip", "duotone"),
    "layout": ("squares-four", "duotone"),
    "izq": ("caret-left", "bold"),
    "der": ("caret-right", "bold"),
    "persona": ("user", "fill"),
    "auto": ("car", "fill"),
    "moto": ("motorcycle", "fill"),
    "bus": ("bus", "fill"),
    "camion": ("truck", "fill"),
    "bici": ("bicycle", "fill"),
    "gato": ("cat", "fill"),
    "perro": ("dog", "fill"),
    "wifi": ("wifi-high", "bold"),
    "wifi_off": ("wifi-slash", "bold"),
    "qr": ("qr-code", "duotone"),
    "descargar": ("download-simple", "bold"),
    "papelera": ("trash", "duotone"),
    "repetir": ("arrow-clockwise", "bold"),
    "volver": ("arrow-left", "bold"),
    "play": ("play-circle", "duotone"),
    "celular": ("device-mobile", "duotone"),
}


def contenido(base, nombre, peso):
    archivo = f"{nombre}.svg" if peso == "regular" else f"{nombre}-{peso}.svg"
    ruta = os.path.join(base, "assets", peso, archivo)
    with open(ruta, encoding="utf-8") as f:
        svg = f.read()
    interior = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    interior = re.sub(r'<rect[^>]*fill="none"[^>]*/>', "", interior)
    return interior.strip()


def main():
    base = sys.argv[1]
    lineas = ['"""Íconos de MeCam: Phosphor Icons (MIT, https://phosphoricons.com), incrustados para funcionar sin internet.',
              'Archivo generado por herramientas/generar_iconos.py: no se edita a mano."""', "", "DATOS = {"]
    for clave, (nombre, peso) in ICONOS.items():
        lineas.append(f"    {clave!r}: {contenido(base, nombre, peso)!r},")
    lineas += ["}", "",
               "", "def _sprite():",
               "    simbolos = ''.join(f'<symbol id=\"i-{k}\" viewBox=\"0 0 256 256\">{v}</symbol>' for k, v in DATOS.items())",
               "    return ('<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"0\" height=\"0\" style=\"position:absolute\" '",
               "            'aria-hidden=\"true\">' + simbolos + '</svg>')", "",
               "", "SPRITE = _sprite()", ""]
    destino = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "servidor", "iconos.py")
    with open(destino, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"{len(ICONOS)} íconos -> {os.path.normpath(destino)}")


if __name__ == "__main__":
    main()
