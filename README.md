# MeCam

Convierte celulares Android viejos en cámaras de seguridad con detección de personas y autos.

## Cómo funciona

1. **App MeCam (Android):** corre en segundo plano (con la pantalla apagada) y transmite video de forma constante a la computadora. Si el celular se calienta, baja la velocidad y, si sigue subiendo, se pausa hasta que se enfríe.
2. **Servidor (computadora):** recibe el video, detecta y sigue personas y autos con YOLO, y los muestra en una página web.

## Instalar la app

1. En el celular, abre la sección **Releases** de este repositorio y descarga `MeCam.apk`.
2. Ábrelo y permite instalar apps de origen desconocido si el celular lo pide.
3. En la app escribe la IP de la computadora y toca **Iniciar cámara**.

## Ejecutar el servidor (Windows)

```
cd servidor
python -m pip install -r requirements.txt
python servidor.py
```

Abre `https://localhost:8443/ver` en la computadora para ver las cámaras. La computadora y los celulares deben estar en la misma red Wi-Fi.

## Estado del proyecto

- [x] Video constante desde el celular
- [x] Detección y seguimiento (YOLO + ByteTrack)
- [x] Varias cámaras a la vez
- [x] Servicio en segundo plano y control de temperatura
- [ ] Audio
- [ ] Alertas (Telegram) y grabación de clips
- [ ] Zonas de alerta
- [ ] Detección dentro del propio celular (sin computadora)

## Privacidad

Grabar personas o la vía pública puede estar regulado (por ejemplo, RGPD en Europa). Úsalo solo en espacios propios y avisa a quien pueda ser grabado.
