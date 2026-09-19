# MeCam

Convierte celulares Android viejos en cámaras de seguridad con detección de personas y autos.

**¿Dudas?** Mira las [preguntas frecuentes](FAQ.md): cómo ver las cámaras desde fuera de casa, cómo evitar el calor, qué hacer si algo falla y más.

## Cómo funciona

1. **App MeCam (Android):** corre en segundo plano (con la pantalla apagada) y transmite video de forma constante a la computadora. Si el celular se calienta, baja la velocidad y, si sigue subiendo, se pausa hasta que se enfríe. Detecta si el celular está vertical u horizontal y adapta la imagen.
2. **Servidor (computadora):** recibe el video, detecta y sigue personas y autos con YOLO, y los muestra en una página web.

El video no sale de tu red: no se sube a ningún servidor de terceros.

## Instalar la app

1. En el celular, abre la sección **Releases** de este repositorio y descarga `MeCam.apk`.
2. Ábrelo y permite instalar apps de origen desconocido si el celular lo pide.
3. En la app toca **Escanear QR para vincular** y apunta al QR que muestra la ventana de MeCam en la computadora (botón **Vincular dispositivo**). Después toca **Iniciar cámara**.

La app avisa cuando hay una versión nueva y se actualiza desde dentro (Android siempre pide confirmar la instalación).

## Ejecutar el servidor (Windows)

1. Instala **Python** desde `python.org/downloads` y marca la casilla **Add python.exe to PATH**.
2. Descarga el proyecto (en esta página, **Code** y luego **Download ZIP**) y extráelo. Abre la carpeta `servidor`.
3. Haz doble clic en **Iniciar MeCam.bat**. La primera vez instala lo necesario y tarda varios minutos.
4. En la ventana de MeCam, haz clic en el botón verde **Iniciar servidor**.
5. Haz clic en **Vincular dispositivo** para que aparezca el QR (uno distinto, de un solo uso, por cada celular).

La ventana abre el centro de control (`https://localhost:8443/ver`) y muestra la lista de dispositivos vinculados. La computadora y los celulares deben estar en la misma red Wi-Fi. Si algo no conecta, usa el botón **Abrir puertos del firewall** (una sola vez) o revisa las [preguntas frecuentes](FAQ.md).

Si prefieres la terminal: `cd servidor`, `python -m pip install -r requirements.txt` y `python servidor.py`.

## Estado del proyecto

- [x] Video constante desde el celular
- [x] Detección y seguimiento (YOLO + ByteTrack)
- [x] Varias cámaras a la vez
- [x] Servicio en segundo plano y control de temperatura
- [x] Orientación automática (vertical/horizontal)
- [x] Actualización desde dentro de la app
- [x] Ventana con botón verde para iniciar y detener el servidor
- [x] Centro de control en el navegador (cuadrícula automática, ampliar, zoom, fotos, alertas y actividad)
- [x] Nombres únicos por cámara y limpieza automática de cámaras desconectadas
- [ ] Audio
- [ ] Alertas (Telegram) y grabación de clips
- [ ] Zonas de alerta
- [x] Vinculación por QR: un código distinto y de un solo uso por dispositivo, con conexión cifrada
- [ ] Detección dentro del propio celular (sin computadora)

## Seguridad y privacidad

- Cuando vinculas el primer dispositivo, MeCam se **protege**: solo entran los dispositivos vinculados con un QR (además de esta computadora y de tu red Tailscale). Mientras no hayas vinculado nada, la ventana muestra «Abierto». **No abras puertos en tu router.** Para verlas desde fuera de casa usa una VPN, como se explica en las [preguntas frecuentes](FAQ.md).
- Grabar personas o la vía pública puede estar regulado (por ejemplo, RGPD en Europa). Úsalo solo en espacios propios y avisa a quien pueda ser grabado.
