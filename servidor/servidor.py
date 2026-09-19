"""
MeCam - sistema de cámaras de seguridad con celulares.

- Celular: abre https://IP-DE-LA-PC:8443 en Chrome y toca "Iniciar cámara".
- Computadora: abre https://localhost:8443/ver para ver el video con detecciones.

Requisitos:  pip install ultralytics aiohttp cryptography
Ejecutar:    python servidor.py
"""
import asyncio
import datetime
import ipaddress
import os
import socket
import ssl

import cv2
import numpy as np
from aiohttp import web
from ultralytics import YOLO

PORT = 8443
MODELO = "yolo11n.pt"
# Clases a detectar: 0 persona, 1 bicicleta, 2 auto, 3 moto, 5 bus, 7 camión
CLASES = [0, 2]
BASE = os.path.dirname(os.path.abspath(__file__))

frames = {}  # nombre de cámara -> último fotograma procesado (JPEG)


# ---------------------------------------------------------------- Páginas
PAGINA_CAMARA = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MeCam</title>
<style>
  body{margin:0;background:#111;color:#fff;font-family:sans-serif;text-align:center}
  video{width:100%;max-height:60vh;background:#000}
  button{font-size:20px;padding:14px 28px;margin:10px;border:0;border-radius:12px;background:#2e7d32;color:#fff}
  #estado,#bateria{padding:6px;font-size:16px}
  #negro{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:#000;z-index:10}
</style></head><body>
<video id="video" autoplay playsinline muted></video>
<div id="estado">Listo</div>
<div id="bateria"></div>
<button id="btn">Iniciar cámara</button>
<button id="btnNegro" style="display:none;background:#455a64">Pantalla negra (ahorrar)</button>
<div id="negro"></div>
<script>
const video = document.getElementById('video');
const estado = document.getElementById('estado');
const bateriaEl = document.getElementById('bateria');
const btn = document.getElementById('btn');
const btnNegro = document.getElementById('btnNegro');
const negro = document.getElementById('negro');
const nombre = new URLSearchParams(location.search).get('cam') || 'celular1';

// ---- Transmisión constante ----
const FPS = 10;   // fotogramas por segundo

let ws = null, esperando = false, ultimoEnvio = 0;
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');

function enviar() {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0);
  esperando = true;
  ultimoEnvio = Date.now();
  canvas.toBlob(b => {
    if (ws && ws.readyState === 1) ws.send(b); else esperando = false;
  }, 'image/jpeg', 0.6);
}

function tick() {
  if (ws && ws.readyState === 1 && !(esperando && Date.now() - ultimoEnvio < 5000)) enviar();
  setTimeout(tick, 1000 / FPS);
}

function conectar() {
  ws = new WebSocket('wss://' + location.host + '/ws/' + nombre);
  ws.onopen = () => { estado.textContent = 'Transmitiendo como: ' + nombre; esperando = false; };
  ws.onmessage = () => { esperando = false; };
  ws.onclose = () => { estado.textContent = 'Reconectando...'; setTimeout(conectar, 3000); };
}

async function pantallaEncendida() {
  try { await navigator.wakeLock.request('screen'); } catch (e) {}
}
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') pantallaEncendida();
});

if (navigator.getBattery) {
  navigator.getBattery().then(b => {
    const mostrar = () => {
      bateriaEl.textContent = 'Batería: ' + Math.round(b.level * 100) + '% ' +
        (b.charging ? '(cargando)' : '(sin cargador)');
    };
    mostrar();
    b.onlevelchange = mostrar;
    b.onchargingchange = mostrar;
  });
}

btnNegro.onclick = () => { negro.style.display = 'block'; };
negro.onclick = () => { negro.style.display = 'none'; };

btn.onclick = async () => {
  btn.style.display = 'none';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'environment',
        width: { ideal: 640 }, height: { ideal: 480 },
        frameRate: { ideal: 10, max: 15 }
      },
      audio: false   // el audio lo agregamos después
    });
    video.srcObject = stream;
    await video.play();
  } catch (e) {
    estado.textContent = 'Error de cámara: ' + e.message;
    btn.style.display = 'inline-block';
    return;
  }
  pantallaEncendida();
  btnNegro.style.display = 'inline-block';
  conectar();
  tick();
};
</script></body></html>
"""

PAGINA_VER = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<title>MeCam - Cámaras</title>
<style>
  body{margin:0;background:#111;color:#fff;font-family:sans-serif}
  #grid{display:flex;flex-wrap:wrap;gap:8px;padding:8px}
  .cam{background:#000;padding:4px}
  .cam img{width:640px;max-width:100%;display:block}
</style></head><body>
<h2 style="padding:8px">MeCam - Cámaras conectadas</h2>
<div id="grid"></div>
<script>
const grid = document.getElementById('grid');
async function actualizar() {
  const lista = await (await fetch('/camaras')).json();
  for (const c of lista) {
    if (!document.getElementById('cam-' + c)) {
      const d = document.createElement('div');
      d.className = 'cam'; d.id = 'cam-' + c;
      d.innerHTML = '<div>' + c + '</div><img src="/stream/' + c + '">';
      grid.appendChild(d);
    }
  }
  for (const d of [...grid.children]) {
    if (!lista.includes(d.id.slice(4))) d.remove();
  }
}
actualizar(); setInterval(actualizar, 2000);
</script></body></html>
"""


# ---------------------------------------------------------------- Procesamiento
def procesar(model, datos):
    """Recibe un JPEG, detecta y sigue objetos, devuelve el JPEG con los recuadros."""
    img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    r = model.track(
        img, persist=True, classes=CLASES,
        tracker="bytetrack.yaml", verbose=False,
    )[0]
    ok, buf = cv2.imencode(".jpg", r.plot())
    return buf.tobytes() if ok else None


# ---------------------------------------------------------------- Rutas web
async def pagina_camara(request):
    return web.Response(text=PAGINA_CAMARA, content_type="text/html")


async def pagina_ver(request):
    return web.Response(text=PAGINA_VER, content_type="text/html")


async def lista_camaras(request):
    return web.json_response(list(frames.keys()))


async def ws_camara(request):
    cam = request.match_info["cam"]
    ws = web.WebSocketResponse(max_msg_size=10 * 1024 * 1024)
    await ws.prepare(request)
    loop = asyncio.get_running_loop()
    # Cada cámara tiene su propio modelo, así el seguimiento no se mezcla
    model = await loop.run_in_executor(None, YOLO, MODELO)
    frames[cam] = b""
    print(f"[+] Cámara conectada: {cam}")
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.BINARY:
                jpg = await loop.run_in_executor(None, procesar, model, msg.data)
                if jpg:
                    frames[cam] = jpg
                await ws.send_str("ok")
    finally:
        frames.pop(cam, None)
        print(f"[-] Cámara desconectada: {cam}")
    return ws


async def stream(request):
    cam = request.match_info["cam"]
    resp = web.StreamResponse(
        headers={"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
    )
    await resp.prepare(request)
    try:
        while cam in frames:
            jpg = frames.get(cam)
            if jpg:
                await resp.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                )
            await asyncio.sleep(0.05)
    except Exception:
        pass
    return resp


# ---------------------------------------------------------------- Certificado HTTPS
def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def crear_certificado(ip):
    """El celular exige HTTPS para dar acceso a la cámara. Creamos un certificado propio."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.IPAddress(ipaddress.ip_address(ip)),
                x509.DNSName("localhost"),
            ]),
            critical=False,
        )
        .sign(clave, hashes.SHA256())
    )
    ruta_cert = os.path.join(BASE, "certificado.pem")
    ruta_clave = os.path.join(BASE, "clave.pem")
    with open(ruta_cert, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(ruta_clave, "wb") as f:
        f.write(clave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    return ruta_cert, ruta_clave


PORT_HTTP = 8080  # para la app de Android (sin certificado)


async def iniciar(ctx, ip):
    app = web.Application()
    app.add_routes([
        web.get("/", pagina_camara),
        web.get("/ver", pagina_ver),
        web.get("/camaras", lista_camaras),
        web.get("/ws/{cam}", ws_camara),
        web.get("/stream/{cam}", stream),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT, ssl_context=ctx).start()
    await web.TCPSite(runner, "0.0.0.0", PORT_HTTP).start()
    print("=" * 50)
    print("MeCam")
    print(f"En el CELULAR (navegador): https://{ip}:{PORT}")
    print(f"En la APP de Android, IP:  {ip}")
    print(f"En la COMPUTADORA abre:    https://localhost:{PORT}/ver")
    print("Para otra cámara agrega:   ?cam=celular2")
    print("=" * 50)
    while True:
        await asyncio.sleep(1)


def main():
    ip = ip_local()
    ruta_cert, ruta_clave = crear_certificado(ip)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ruta_cert, ruta_clave)
    try:
        asyncio.run(iniciar(ctx, ip))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
