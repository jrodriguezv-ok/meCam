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
3. En la app escribe la IP de la computadora y un nombre para la cámara (distinto en cada celular), y toca **Iniciar cámara**.

La app avisa cuando hay una versión nueva y se actualiza desde dentro (Android siempre pide confirmar la instalación).

## Ejecutar el servidor (Windows)

```
cd servidor
python -m pip install -r requirements.txt
python servidor.py
```

Abre `https://localhost:8443/ver` en la computadora para ver las cámaras. La computadora y los celulares deben estar en la misma red Wi-Fi. Si algo no conecta, revisa las [preguntas frecuentes](FAQ.md) (suele ser el firewall de Windows).

## Estado del proyecto

- [x] Video constante desde el celular
- [x] Detección y seguimiento (YOLO + ByteTrack)
- [x] Varias cámaras a la vez
- [x] Servicio en segundo plano y control de temperatura
- [x] Orientación automática (vertical/horizontal)
- [x] Actualización desde dentro de la app
- [x] Centro de control en el navegador (cuadrícula automática, ampliar, zoom, fotos, alertas y actividad)
- [x] Nombres únicos por cámara y limpieza automática de cámaras desconectadas
- [ ] Audio
- [ ] Alertas (Telegram) y grabación de clips
- [ ] Zonas de alerta
- [ ] Usuario y contraseña para ver las cámaras
- [ ] Detección dentro del propio celular (sin computadora)

## Seguridad y privacidad

- Hoy la página de visualización **no pide contraseña**: cualquiera dentro de tu Wi-Fi que conozca la dirección puede ver las cámaras. **No abras puertos en tu router.** Para verlas desde fuera de casa usa una VPN, como se explica en las [preguntas frecuentes](FAQ.md).
- Grabar personas o la vía pública puede estar regulado (por ejemplo, RGPD en Europa). Úsalo solo en espacios propios y avisa a quien pueda ser grabado.
