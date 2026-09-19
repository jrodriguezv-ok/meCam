"""
MeCam - servidor.

- Celular: app MeCam (o https://IP-DE-LA-PC:8443 en el navegador) -> transmite video.
- Computadora / celular: https://localhost:8443/ver  -> centro de control con todas las cámaras.

Requisitos:  python -m pip install -r requirements.txt
Ejecutar:    python servidor.py
"""
import asyncio
import datetime
import ipaddress
import itertools
import os
import re
import socket
import ssl
import threading
import time
from collections import deque

import cv2
import numpy as np
from aiohttp import web
from ultralytics import YOLO

import grabaciones
import iconos
import vinculos

PORT = 8443        # navegador (HTTPS)
PORT_HTTP = 8080   # app de Android (sin certificado)
MODELO = "yolo11n.pt"
# Clases a detectar: 0 persona, 1 bicicleta, 2 auto, 3 moto, 5 bus, 7 camión, 15 gato, 16 perro
CLASES = [0, 2]
BASE = os.path.dirname(os.path.abspath(__file__))
SEGS_EN_VIVO = 4   # sin imágenes durante más de estos segundos = "sin señal"

NOMBRES = {  # nombre en inglés del modelo -> (singular, plural)
    "person": ("persona", "personas"),
    "bicycle": ("bicicleta", "bicicletas"),
    "car": ("auto", "autos"),
    "motorcycle": ("moto", "motos"),
    "bus": ("bus", "buses"),
    "truck": ("camión", "camiones"),
    "cat": ("gato", "gatos"),
    "dog": ("perro", "perros"),
}
SINGULAR = {plural: singular for singular, plural in NOMBRES.values()}

camaras = {}                 # nombre -> Camara (solo las conectadas ahora)
eventos = deque(maxlen=100)  # registro de actividad (lo más nuevo primero)
_id_evento = itertools.count(1)
_id_cuadro = itertools.count(1)
IP_LOCAL = "127.0.0.1"
parando = False             # True mientras el servidor se está deteniendo
registro = vinculos.Registro()   # dispositivos vinculados por QR
grabador = grabaciones.Grabador(al_guardar=lambda texto: evento(texto))   # clips cuando se detecta una persona


class Camara:
    """Una cámara conectada. Cada celular tiene su propia ficha, así nunca se pisan."""

    def __init__(self, nombre, disp_id, ws):
        self.nombre = nombre
        self.id = disp_id          # identificador del celular (para reconocerlo al reconectar)
        self.ws = ws
        self.jpg = b""             # último cuadro con recuadros
        self.crudo = b""           # último cuadro sin recuadros
        self.n = 0                 # número del último cuadro
        self.ultimo = 0.0          # cuándo llegó el último cuadro
        self.fps = 0.0
        self.res = ""
        self.conteo = {}
        self.previo = {}
        self.ultima_alerta = {}
        self.desde = time.time()

    async def cerrar(self):
        try:
            await self.ws.close()
        except Exception:
            pass


def evento(texto):
    eventos.appendleft({"id": next(_id_evento), "hora": time.strftime("%H:%M:%S"), "texto": texto})


def limpiar_nombre(nombre):
    nombre = re.sub(r"[^\w\- .]", "", nombre).strip()[:32]
    return nombre or "camara"


# ---------------------------------------------------------------- Páginas
PAGINA_CAMARA = r"""<!DOCTYPE html>
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
// Identificador propio de este celular: así el servidor sabe que es el mismo al reconectar
const idDisp = (function () {
  try {
    let v = localStorage.getItem('mecam_id');
    if (!v) { v = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('mecam_id', v); }
    return v;
  } catch (e) { return ''; }
})();

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
  ws = new WebSocket('wss://' + location.host + '/ws/' + encodeURIComponent(nombre) + '?id=' + idDisp);
  ws.onopen = () => { estado.textContent = 'Transmitiendo como: ' + nombre; esperando = false; };
  ws.onmessage = (e) => {
    if (typeof e.data === 'string' && e.data.indexOf('nombre:') === 0) {
      estado.textContent = 'Transmitiendo como: ' + e.data.slice(7);
      return;
    }
    esperando = false;
  };
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

PAGINA_VER = r"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a0e14">
<title>MeCam · Centro de control</title>
<style>
:root{
  --bg:#0a0e14; --panel:#111823; --panel2:#172131; --borde:#233047;
  --texto:#e8eef6; --suave:#8a9bb3; --acento:#38bdf8;
  --ok:#34d399; --alerta:#f87171; --aviso:#fbbf24; --radio:14px;
}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{
  background:radial-gradient(1100px 500px at 8% -10%, #0f2438 0%, transparent 60%), var(--bg);
  color:var(--texto);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  display:flex;flex-direction:column;overflow:hidden;
}
button{font:inherit;color:inherit;cursor:pointer}
svg{width:16px;height:16px;fill:currentColor;flex:none}

/* ---------- Barra superior ---------- */
#barra{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:10px 16px;padding-top:calc(10px + env(safe-area-inset-top,0px));
  background:rgba(17,24,35,.85);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--borde);
}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;letter-spacing:.3px}
.logo .logo-ic{display:grid;place-items:center}
.logo .logo-ic svg{width:30px;height:30px;color:var(--acento);filter:drop-shadow(0 0 8px rgba(56,189,248,.5))}
.logo small{color:var(--suave);font-weight:500;font-size:12px;letter-spacing:.4px}
.pill{
  display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:999px;
  background:var(--panel2);border:1px solid var(--borde);font-size:12.5px;color:var(--suave);white-space:nowrap;
  font-variant-numeric:tabular-nums;
}
.pill b{color:var(--texto);font-weight:600}
.punto{width:8px;height:8px;border-radius:50%;background:var(--aviso);box-shadow:0 0 8px var(--aviso)}
.pill.ok .punto{background:var(--ok);box-shadow:0 0 8px var(--ok)}
.pill.mal .punto{background:var(--alerta);box-shadow:0 0 8px var(--alerta)}
.espacio{flex:1}
.grupo{display:inline-flex;background:var(--panel2);border:1px solid var(--borde);border-radius:10px;overflow:hidden}
.grupo button{border:0;background:transparent;padding:7px 12px;font-size:13px;color:var(--suave)}
.grupo button.on{background:var(--acento);color:#04121f;font-weight:700}
.btn{
  display:inline-flex;align-items:center;gap:7px;padding:7px 12px;border-radius:10px;
  border:1px solid var(--borde);background:var(--panel2);color:var(--texto);font-size:13px;
}
.btn:hover{border-color:var(--acento)}
.btn.on{background:rgba(56,189,248,.15);border-color:var(--acento);color:var(--acento)}

/* ---------- Botones flotantes ---------- */
#dock{
  position:fixed;right:16px;top:50%;transform:translateY(-50%);z-index:15;
  display:flex;flex-direction:column;gap:10px;padding:10px;border-radius:24px;
  background:rgba(17,24,35,.72);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  border:1px solid rgba(255,255,255,.09);box-shadow:0 16px 44px rgba(0,0,0,.5);
}
.fab{
  position:relative;width:48px;height:48px;border-radius:50%;display:grid;place-items:center;padding:0;
  border:1px solid var(--borde);background:var(--panel2);color:var(--texto);text-decoration:none;
  transition:transform .15s,border-color .15s,background .15s,box-shadow .15s,color .15s;
}
.fab svg{width:26px;height:26px}
.fab:hover{transform:scale(1.08);border-color:var(--acento);color:var(--acento)}
.fab:active{transform:scale(.96)}
.fab:focus-visible{outline:2px solid var(--acento);outline-offset:2px}
.fab.on{background:rgba(56,189,248,.18);border-color:var(--acento);color:var(--acento);box-shadow:0 0 18px rgba(56,189,248,.35)}
.fab::after{
  content:attr(data-tip);position:absolute;right:calc(100% + 12px);top:50%;transform:translateY(-50%);
  white-space:nowrap;background:#0b111a;border:1px solid var(--borde);color:var(--texto);
  padding:6px 10px;border-radius:8px;font-size:12.5px;font-weight:500;opacity:0;pointer-events:none;transition:opacity .15s;
}
.fab:hover::after,.fab:focus-visible::after{opacity:1}
.fab .punto-nuevo{position:absolute;top:5px;right:5px;width:11px;height:11px;border-radius:50%;background:var(--alerta);border:2px solid var(--panel2);display:none}
.fab .valor{
  position:absolute;right:-3px;bottom:-3px;min-width:20px;height:20px;border-radius:10px;padding:0 5px;
  background:var(--acento);color:#04121f;font-size:11px;font-weight:800;display:grid;place-items:center;
}
@media (max-width:700px){
  #dock{
    right:auto;left:50%;top:auto;bottom:calc(14px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);
    flex-direction:row;gap:8px;padding:8px;border-radius:28px;
  }
  .fab{width:46px;height:46px}
  .fab::after{display:none}
}
.vacio-ic svg{width:68px;height:68px;color:var(--acento);filter:drop-shadow(0 0 14px rgba(56,189,248,.45))}
#vacio ol{text-align:left;color:var(--suave);line-height:1.6;padding-left:22px;margin:10px 0}
#vacio .chico{font-size:13px}
.evic{display:grid;place-items:center;flex:none;margin-top:1px}
.evic svg{width:18px;height:18px}
.evic.alerta{color:var(--alerta)}.evic.ok{color:var(--ok)}.evic.info{color:var(--acento)}.evic.suave{color:var(--suave)}

/* ---------- Cuadrícula de cámaras ---------- */
#grid{
  flex:1;min-height:0;display:grid;gap:10px;padding:10px;overflow:auto;
  padding-bottom:calc(10px + env(safe-area-inset-bottom,0px));
}
.tile{
  position:relative;background:#000;border:1px solid var(--borde);border-radius:var(--radio);
  overflow:hidden;min-height:0;cursor:pointer;outline:none;
  transition:box-shadow .2s,border-color .2s;
}
.tile:focus-visible{border-color:var(--acento)}
.tile img.video{width:100%;height:100%;object-fit:contain;display:block;background:#000}
.tile.alerta{border-color:var(--alerta);box-shadow:0 0 0 1px var(--alerta),0 0 26px rgba(248,113,113,.35)}
.tile.offline img.video{filter:grayscale(1) brightness(.45)}
.arriba,.abajo{position:absolute;left:0;right:0;display:flex;align-items:center;gap:8px;padding:10px 12px;pointer-events:none}
.arriba{top:0;background:linear-gradient(#000c,#0000)}
.abajo{bottom:0;background:linear-gradient(#0000,#000c);flex-wrap:wrap}
.nombre{font-weight:600;font-size:14px;text-shadow:0 1px 3px #000;max-width:55%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.estado{font-size:11px;font-weight:700;letter-spacing:.6px;padding:3px 8px;border-radius:999px;background:#0008;border:1px solid #fff2}
.estado.vivo{color:var(--ok)}
.estado.vivo::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);margin-right:6px;box-shadow:0 0 8px var(--ok);animation:latido 1.8s ease-in-out infinite}
@keyframes latido{50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
.estado.sin{color:var(--aviso)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:3px 9px;border-radius:999px;background:rgba(248,113,113,.2);border:1px solid rgba(248,113,113,.55);color:#ffd9d9}
.chip svg{width:14px;height:14px}
.chip.auto{background:rgba(56,189,248,.18);border-color:rgba(56,189,248,.55);color:#d3efff}
.meta{margin-left:auto;font-size:11.5px;color:#cbd5e1;font-variant-numeric:tabular-nums;text-shadow:0 1px 3px #000}
.acciones{position:absolute;top:8px;right:8px;display:flex;gap:6px;opacity:0;transition:opacity .15s}
.tile:hover .acciones,.tile:focus-within .acciones{opacity:1}
@media (hover:none){.acciones{opacity:1}}
.ic{
  width:38px;height:38px;display:grid;place-items:center;border-radius:11px;
  border:1px solid #ffffff2b;background:#0009;backdrop-filter:blur(6px);color:var(--texto);
}
.ic:hover{border-color:var(--acento);color:var(--acento)}
.ic svg{width:21px;height:21px}

/* ---------- Sin cámaras ---------- */
#vacio{position:fixed;left:0;right:0;bottom:0;top:64px;display:none;place-items:center;padding:24px;pointer-events:none;z-index:1}
#vacio .caja{
  max-width:460px;text-align:center;background:var(--panel);border:1px solid var(--borde);
  border-radius:18px;padding:28px 26px;box-shadow:0 20px 60px #0008;
}
#vacio h2{margin:0 0 8px;font-size:20px}
#vacio p{margin:6px 0;color:var(--suave);line-height:1.5}
#vacio code{background:var(--panel2);padding:2px 8px;border-radius:6px;color:var(--acento);font-size:15px}

/* ---------- Panel de actividad ---------- */
#actividad{
  position:fixed;top:0;right:0;bottom:0;width:min(360px,100%);background:var(--panel);
  border-left:1px solid var(--borde);transform:translateX(100%);transition:transform .25s;z-index:20;
  display:flex;flex-direction:column;
}
#actividad.abierto{transform:none}
#actividad header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 16px;padding-top:calc(14px + env(safe-area-inset-top,0px));
  border-bottom:1px solid var(--borde);font-weight:600;
}
#lista{flex:1;overflow:auto;padding:8px 6px}
.ev{display:flex;gap:10px;padding:9px 12px;border-radius:10px;font-size:13.5px;line-height:1.35}
.ev:hover{background:var(--panel2)}
.ev time{color:var(--suave);font-variant-numeric:tabular-nums;flex:none}
.ev.nuevo{animation:parpadeo 1.6s ease-out}
@keyframes parpadeo{from{background:rgba(56,189,248,.25)}to{background:transparent}}
#sinEv{color:var(--suave);padding:20px;text-align:center;font-size:14px}

/* ---------- Vista ampliada ---------- */
#foco{position:fixed;inset:0;z-index:30;background:rgba(4,7,11,.985);display:flex;flex-direction:column}
#foco[hidden]{display:none}
#focoBarra{
  display:flex;align-items:center;gap:8px;flex-wrap:wrap;
  padding:10px 14px;padding-top:calc(10px + env(safe-area-inset-top,0px));
}
#focoBarra strong{font-size:16px}
#visor{position:relative;flex:1;min-height:0;overflow:hidden;touch-action:none;display:grid;place-items:center}
#visor img{max-width:100%;max-height:100%;transform-origin:center;user-select:none;-webkit-user-drag:none;will-change:transform}
#tiras{
  display:flex;gap:8px;padding:10px 14px;overflow-x:auto;
  padding-bottom:calc(10px + env(safe-area-inset-bottom,0px));
}
.mini{
  flex:0 0 auto;width:124px;height:74px;border-radius:10px;overflow:hidden;border:2px solid var(--borde);
  position:relative;background:#000;cursor:pointer;
}
.mini.activa{border-color:var(--acento)}
.mini img{width:100%;height:100%;object-fit:cover;display:block}
.mini span{position:absolute;left:6px;bottom:4px;font-size:11px;text-shadow:0 1px 3px #000;max-width:90%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

/* ---------- Controles flotantes de la vista ampliada ---------- */
#focoCuerpo{position:relative;flex:1;min-height:0;display:flex}
#focoCuerpo #visor{flex:1}
.flecha{
  position:absolute;top:50%;transform:translateY(-50%);z-index:2;width:54px;height:54px;border-radius:50%;
  display:grid;place-items:center;padding:0;color:var(--texto);
  background:rgba(17,24,35,.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid rgba(255,255,255,.13);transition:transform .15s,border-color .15s,color .15s;
}
.flecha svg{width:28px;height:28px}
.flecha.izq{left:14px}.flecha.der{right:14px}
.flecha:hover{border-color:var(--acento);color:var(--acento);transform:translateY(-50%) scale(1.08)}
#focoDock{
  position:absolute;left:50%;bottom:16px;transform:translateX(-50%);z-index:2;
  display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;
  background:rgba(17,24,35,.78);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  border:1px solid rgba(255,255,255,.1);box-shadow:0 14px 40px rgba(0,0,0,.6);
}
#focoDock .fab{width:44px;height:44px}
#focoDock .fab svg{width:24px;height:24px}
#focoDock .fab::after{right:auto;left:50%;top:auto;bottom:calc(100% + 12px);transform:translateX(-50%)}
#focoDock .sep{width:1px;height:26px;background:var(--borde);margin:0 4px}
@media (max-width:700px){
  .flecha{width:46px;height:46px}.flecha.izq{left:8px}.flecha.der{right:8px}
  #focoDock{gap:4px;padding:6px 8px}#focoDock .fab{width:40px;height:40px}#focoDock .fab::after{display:none}
}

/* ---------- Aviso emergente ---------- */
#toast{
  position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:var(--panel2);
  border:1px solid var(--borde);padding:10px 16px;border-radius:12px;opacity:0;transition:.25s;
  z-index:60;pointer-events:none;font-size:14px;box-shadow:0 10px 30px #0008;
}
#toast.ver{opacity:1;transform:translateX(-50%)}

@media (max-width:700px){
  #toast{bottom:calc(96px + env(safe-area-inset-bottom,0px))}
  #barra{gap:8px;padding:8px 12px}
  .logo small{display:none}
  .btn{padding:8px 10px}
  #reloj{display:none}
  .mini{width:104px;height:64px}
}
.rec{
  display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:800;letter-spacing:.6px;padding:3px 8px;
  border-radius:999px;background:#0008;border:1px solid #fff3;color:var(--suave);cursor:pointer;pointer-events:auto;
}
.rec::before{content:"";width:8px;height:8px;border-radius:50%;border:2px solid currentColor;box-sizing:border-box}
.rec:hover{border-color:var(--acento)}
.rec.grabando{color:#fff;background:rgba(239,68,68,.88);border-color:#ef4444}
.rec.grabando::before{background:#fff;border-color:#fff;animation:latido 1s ease-in-out infinite}
.rec.lista{color:#fca5a5;border-color:rgba(239,68,68,.55)}
.rec.excluida{color:#94a3b8;text-decoration:line-through}
.rec.off{display:none}
.fab.rec-on{background:rgba(239,68,68,.16);border-color:#ef4444;color:#f87171;box-shadow:0 0 18px rgba(239,68,68,.4)}
@media (max-width:700px){#dock{gap:6px;padding:7px}.fab{width:42px;height:42px}.fab svg{width:24px;height:24px}}
/* el espacio para los botones flotantes va al final para ganarle a la regla base de #grid */
@media (min-width:701px){#grid{padding-right:86px}}
@media (max-width:700px){#grid{padding-bottom:calc(92px + env(safe-area-inset-bottom,0px))}}
</style></head><body>

<!--SPRITE-->
<header id="barra">
  <div class="logo"><span class="logo-ic" data-i="logo"></span><span>MeCam</span><small>Centro de control</small></div>
  <span class="pill" id="pSrv"><span class="punto"></span><b id="pSrvTxt">Conectando…</b></span>
  <span class="pill"><b id="nCams">0</b> cámaras · <b id="nVivo">0</b> en vivo</span>
  <span class="pill" id="reloj"></span>
  <span class="espacio"></span>
</header>

<main id="grid"></main>

<nav id="dock" aria-label="Acciones del centro de control">
  <a class="fab" href="/grabaciones" data-i="grabaciones" data-tip="Grabaciones (G)" aria-label="Grabaciones"></a>
  <button class="fab" id="bRec" data-i="rec" data-tip="Grabación de clips (Q)" aria-label="Grabación de clips" aria-pressed="true"></button>
  <button class="fab" id="bAct" data-i="actividad" data-tip="Actividad (A)" aria-label="Actividad"><i class="punto-nuevo" id="badgeAct"></i></button>
  <button class="fab" id="bSonido" data-i="campana_off" data-tip="Alerta sonora (S)" aria-label="Alerta sonora" aria-pressed="false"></button>
  <button class="fab" id="bRaw" data-i="recuadro" data-tip="Ver sin recuadros (R)" aria-label="Ver sin recuadros" aria-pressed="false"></button>
  <button class="fab" id="bLayout" data-i="layout" data-tip="Distribución de las cámaras (L)" aria-label="Distribución de las cámaras"><b class="valor" id="valLayout">A</b></button>
  <button class="fab" id="bPantalla" data-i="ampliar" data-tip="Pantalla completa (F)" aria-label="Pantalla completa"></button>
</nav>

<div id="vacio">
  <div class="caja">
    <div class="vacio-ic" data-i="logo"></div>
    <h2>Esperando cámaras…</h2>
    <p>Para conectar un celular:</p>
    <ol>
      <li>En la computadora, en la ventana de <b>MeCam</b>, toca <b>Vincular dispositivo</b>.</li>
      <li>En el celular, abre <b>MeCam</b> y toca <b>Escanear QR para vincular</b>.</li>
    </ol>
    <p>Aparecerá aquí solo, con su propio nombre.</p>
    <p class="chico">IP de esta computadora (solo para la conexión manual): <code id="vacioIp">—</code></p>
  </div>
</div>

<aside id="actividad" aria-label="Registro de actividad">
  <header><span>Actividad reciente</span><button class="ic" id="aCerrar" data-i="cerrar" title="Cerrar" aria-label="Cerrar"></button></header>
  <div id="lista"><div id="sinEv">Todavía no hay actividad.</div></div>
</aside>

<div id="foco" hidden>
  <div id="focoBarra">
    <button class="ic" id="fCerrar" data-i="cerrar" title="Cerrar (Esc)" aria-label="Cerrar"></button>
    <strong id="focoNombre"></strong>
    <span class="estado sin" id="focoEstado">SIN SEÑAL</span>
    <span class="chips" id="focoChips"></span>
    <span class="rec off" id="focoRec">REC</span>
    <span class="espacio"></span>
  </div>
  <div id="focoCuerpo">
    <div id="visor"><img id="focoImg" alt="" draggable="false"></div>
    <button class="flecha izq" id="fPrev" data-i="izq" title="Cámara anterior (←)" aria-label="Cámara anterior"></button>
    <button class="flecha der" id="fNext" data-i="der" title="Cámara siguiente (→)" aria-label="Cámara siguiente"></button>
    <div id="focoDock">
      <button class="fab" id="fMenos" data-i="menos" data-tip="Alejar (−)" aria-label="Alejar"></button>
      <span class="pill" id="fZoom">100%</span>
      <button class="fab" id="fMas" data-i="mas" data-tip="Acercar (+)" aria-label="Acercar"></button>
      <button class="fab" id="fReset" data-i="reset" data-tip="Zoom normal (0)" aria-label="Restablecer zoom"></button>
      <span class="sep"></span>
      <button class="fab" id="fFoto" data-i="camara" data-tip="Capturar foto (C)" aria-label="Capturar foto"></button>
      <button class="fab" id="fPant" data-i="ampliar" data-tip="Pantalla completa (F)" aria-label="Pantalla completa"></button>
    </div>
  </div>
  <div id="tiras"></div>
</div>

<div id="toast" role="status"></div>

<script>
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);

  const SING = { personas: 'persona', autos: 'auto', motos: 'moto', buses: 'bus', camiones: 'camión',
                 bicicletas: 'bicicleta', gatos: 'gato', perros: 'perro' };
  // Los íconos (Phosphor) vienen en un sprite incrustado en la página: no hace falta internet
  function svg(n) { return '<svg viewBox="0 0 256 256" aria-hidden="true"><use href="#i-' + n + '"/></svg>'; }
  function cambiarIcono(el, n) { const u = el.querySelector('use'); if (u) u.setAttribute('href', '#i-' + n); }
  document.querySelectorAll('[data-i]').forEach(function (e) { e.insertAdjacentHTML('afterbegin', svg(e.dataset.i)); });
  const ICONO_CHIP = { personas: 'persona', autos: 'auto', motos: 'moto', buses: 'bus', camiones: 'camion',
                       bicicletas: 'bici', gatos: 'gato', perros: 'perro' };

  // ---- Preferencias del visor (se guardan en este navegador)
  const CLAVE = 'mecam_visor';
  const prefs = { cols: 'auto', raw: false, sonido: false };
  try { Object.assign(prefs, JSON.parse(localStorage.getItem(CLAVE) || '{}')); } catch (e) {}
  function guardar() { try { localStorage.setItem(CLAVE, JSON.stringify(prefs)); } catch (e) {} }

  const grid = $('#grid');
  const tiles = new Map();          // nombre -> { el, img, ... }
  let camaras = [];                 // último estado recibido del servidor
  let enLinea = null;               // null = todavía sin dato
  let eventosPrev = -1;
  let eventosVistos = -1;           // hasta qué evento ya vio la persona (para el punto rojo)
  let grabacionActiva = true;       // interruptor general de la grabación de clips
  const foco = { nombre: null, zoom: 1, x: 0, y: 0 };

  function urlStream(n, extra) {
    const q = [];
    if (prefs.raw) q.push('raw=1');
    if (extra) q.push(extra);
    return '/stream/' + encodeURIComponent(n) + (q.length ? '?' + q.join('&') : '');
  }
  function urlFoto(n, extra) {
    const q = [];
    if (prefs.raw) q.push('raw=1');
    if (extra) q.push(extra);
    return '/foto/' + encodeURIComponent(n) + (q.length ? '?' + q.join('&') : '');
  }

  // ---- Aviso emergente
  let toastT = null;
  function aviso(texto) {
    const t = $('#toast');
    t.textContent = texto;
    t.classList.add('ver');
    clearTimeout(toastT);
    toastT = setTimeout(function () { t.classList.remove('ver'); }, 2600);
  }

  // ---- Video en directo (un <img> por cámara). Si se corta, se reintenta solo.
  function conectarImg(img, nombre, esFoco) {
    img.onerror = function () {
      setTimeout(function () {
        const sigue = esFoco ? foco.nombre === nombre : tiles.has(nombre);
        if (sigue) img.src = urlStream(nombre, 't=' + Date.now());
      }, 2000);
    };
    img.src = urlStream(nombre, 't=' + Date.now());   // dirección única: evita que el navegador reutilice un video viejo
  }
  function recargarStreams() {
    tiles.forEach(function (t) { conectarImg(t.img, t.nombre, false); });
    if (foco.nombre) conectarImg($('#focoImg'), foco.nombre, true);
  }

  // ---- Chips de detección (personas, autos...)
  function pintarChips(cont, conteo) {
    cont.textContent = '';
    Object.keys(conteo || {}).forEach(function (k) {
      const v = conteo[k];
      if (!v) return;
      const s = document.createElement('span');
      s.className = 'chip' + (k === 'personas' ? '' : ' auto');
      s.insertAdjacentHTML('afterbegin', svg(ICONO_CHIP[k] || 'pulse'));
      s.appendChild(document.createTextNode(v + ' ' + (v === 1 ? (SING[k] || k) : k)));
      cont.appendChild(s);
    });
  }

  // ---- Indicador REC de cada cámara (también es el selector de esa cámara)
  const TXT_REC = {
    grabando: 'Grabando un clip ahora. Toca para dejar de grabar esta cámara',
    lista: 'Esta cámara graba un clip cuando detecta una persona. Toca para dejar de grabarla',
    excluida: 'Esta cámara no graba. Toca para volver a grabarla'
  };
  function pintarRecPill(el, estado) {
    el.className = 'rec ' + (estado || 'off');
    el.title = TXT_REC[estado] || '';
    el.setAttribute('aria-label', el.title);
  }

  // ---- Cada cámara es una "ficha" de la cuadrícula
  function crearTile(nombre) {
    const el = document.createElement('div');
    el.className = 'tile';
    el.tabIndex = 0;
    el.innerHTML =
      '<img class="video" alt="">' +
      '<div class="arriba"><span class="nombre"></span><span class="estado sin">SIN SEÑAL</span><span class="rec off">REC</span></div>' +
      '<div class="acciones">' +
        '<button class="ic" data-a="foto" title="Capturar foto" aria-label="Capturar foto">' + svg('camara') + '</button>' +
        '<button class="ic" data-a="ampliar" title="Ampliar" aria-label="Ampliar">' + svg('ampliar') + '</button>' +
      '</div>' +
      '<div class="abajo"><span class="chips"></span><span class="meta"></span></div>';
    const t = {
      el: el, nombre: nombre,
      img: el.querySelector('img'), nom: el.querySelector('.nombre'), est: el.querySelector('.estado'),
      chips: el.querySelector('.chips'), meta: el.querySelector('.meta'), rec: el.querySelector('.rec'), personas: false
    };
    t.nom.textContent = nombre;
    t.img.alt = 'Cámara ' + nombre;
    el.addEventListener('click', function (e) {
      if (e.target.closest('.rec')) { e.stopPropagation(); alternarRecCamara(nombre); return; }
      const b = e.target.closest('button');
      if (b && b.dataset.a === 'foto') { e.stopPropagation(); capturar(nombre); return; }
      abrirFoco(nombre);
    });
    el.addEventListener('keydown', function (e) { if (e.key === 'Enter') abrirFoco(nombre); });
    conectarImg(t.img, nombre, false);
    grid.appendChild(el);
    tiles.set(nombre, t);
    return t;
  }

  function actualizarTile(t, c) {
    const vivo = !!c.en_vivo;
    const personas = (c.conteo && c.conteo.personas) || 0;
    t.est.textContent = vivo ? 'EN VIVO' : 'SIN SEÑAL';
    t.est.className = 'estado ' + (vivo ? 'vivo' : 'sin');
    t.el.classList.toggle('offline', !vivo);
    t.el.classList.toggle('alerta', vivo && personas > 0);
    pintarChips(t.chips, vivo ? c.conteo : {});
    t.meta.textContent = vivo ? (c.fps.toFixed(1) + ' fps · ' + c.res) : 'sin imágenes recientes';
    pintarRecPill(t.rec, c.rec);
  }

  // ---- Distribución de la cuadrícula
  function layout() {
    const n = tiles.size;
    const ancho = window.innerWidth;
    let cols;
    if (prefs.cols !== 'auto') cols = Math.min(parseInt(prefs.cols, 10) || 1, Math.max(n, 1));
    else if (n <= 1) cols = 1;
    else if (ancho < 700) cols = n <= 2 ? 1 : 2;
    else if (n <= 4) cols = 2;
    else if (n <= 9) cols = 3;
    else cols = 4;
    const filas = Math.max(1, Math.ceil(n / cols));
    grid.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
    grid.style.gridTemplateRows = 'repeat(' + filas + ', minmax(' + (ancho < 700 ? 200 : 230) + 'px, 1fr))';
  }

  // ---- Registro de actividad
  function iconoEvento(texto) {
    const x = texto.toLowerCase();
    if (x.indexOf('detecci') >= 0) return ['persona', 'alerta'];
    if (x.indexOf('clip') >= 0) return ['grabaciones', 'info'];
    if (x.indexOf('desconectada') >= 0) return ['wifi_off', 'suave'];
    if (x.indexOf('conectada') >= 0) return ['wifi', 'ok'];
    if (x.indexOf('vinculad') >= 0) return ['qr', 'info'];
    return ['pulse', 'suave'];
  }
  function pintarEventos(lista, total) {
    const cont = $('#lista');
    cont.textContent = '';
    if (!lista.length) {
      const v = document.createElement('div');
      v.id = 'sinEv';
      v.textContent = 'Todavía no hay actividad.';
      cont.appendChild(v);
      return;
    }
    lista.forEach(function (e, i) {
      const fila = document.createElement('div');
      fila.className = 'ev' + (i === 0 && eventosPrev >= 0 ? ' nuevo' : '');
      const h = document.createElement('time');
      h.textContent = e.hora;
      const tipo = iconoEvento(e.texto);
      const ic = document.createElement('span');
      ic.className = 'evic ' + tipo[1];
      ic.insertAdjacentHTML('afterbegin', svg(tipo[0]));
      const s = document.createElement('span');
      s.textContent = e.texto;
      fila.append(h, ic, s);
      cont.appendChild(fila);
    });
  }

  // ---- Alerta sonora
  let audio = null;
  let ultimoPitido = 0;
  function pitido() {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      if (audio.state === 'suspended') audio.resume();
      const o = audio.createOscillator();
      const g = audio.createGain();
      o.type = 'sine';
      o.frequency.value = 880;
      g.gain.value = 0.08;
      o.connect(g);
      g.connect(audio.destination);
      o.start();
      setTimeout(function () { o.stop(); }, 200);
    } catch (e) {}
  }

  // ---- Estado del servidor (se consulta cada segundo)
  function procesarEstado(d) {
    camaras = d.camaras || [];
    grabacionActiva = d.grabacion !== false;
    pintarRec();
    const nombres = new Set(camaras.map(function (c) { return c.nombre; }));
    let cambio = false;

    camaras.forEach(function (c) { if (!tiles.has(c.nombre)) { crearTile(c.nombre); cambio = true; } });
    tiles.forEach(function (t, n) {
      if (!nombres.has(n)) {           // celular desconectado: su ficha desaparece
        tiles.delete(n);
        t.img.onerror = null;
        t.img.src = '';
        t.el.remove();
        cambio = true;
      }
    });
    camaras.forEach(function (c) {
      const t = tiles.get(c.nombre);
      actualizarTile(t, c);
      const hay = !!(c.en_vivo && c.conteo && c.conteo.personas > 0);
      if (hay && !t.personas && prefs.sonido && Date.now() - ultimoPitido > 8000) {
        ultimoPitido = Date.now();
        pitido();
      }
      t.personas = hay;
    });
    if (cambio) layout();

    $('#nCams').textContent = camaras.length;
    $('#nVivo').textContent = camaras.filter(function (c) { return c.en_vivo; }).length;
    $('#vacio').style.display = camaras.length ? 'none' : 'grid';
    $('#vacioIp').textContent = d.ip || '—';

    if (d.total_eventos !== eventosPrev) {
      pintarEventos(d.eventos || [], d.total_eventos);
      eventosPrev = d.total_eventos;
    }
    if (eventosVistos < 0) eventosVistos = eventosPrev;
    if (eventosPrev > eventosVistos) {
      if ($('#actividad').classList.contains('abierto')) eventosVistos = eventosPrev;
      else $('#badgeAct').style.display = 'block';
    }

    if (foco.nombre) {
      const c = camaras.find(function (x) { return x.nombre === foco.nombre; });
      if (!c) { cerrarFoco(); aviso('La cámara se desconectó'); }
      else infoFoco(c);
      armarTiras();
    }
  }

  function marcarServidor(ok) {
    const p = $('#pSrv');
    p.className = 'pill ' + (ok ? 'ok' : 'mal');
    $('#pSrvTxt').textContent = ok ? 'Servidor en línea' : 'Sin conexión con el servidor';
  }

  function sondear() {
    fetch('/estado', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        const volvio = enLinea === false;
        enLinea = true;
        marcarServidor(true);
        procesarEstado(d);
        if (volvio) recargarStreams();
      })
      .catch(function () {
        if (enLinea !== false) aviso('Se perdió la conexión con el servidor');
        enLinea = false;
        marcarServidor(false);
      })
      .then(function () { setTimeout(sondear, 1000); });
  }

  // ---- Captura de foto
  function capturar(nombre) {
    fetch(urlFoto(nombre, 't=' + Date.now()), { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('sin imagen'); return r.blob(); })
      .then(function (b) {
        const t = new Date();
        const p = function (n) { return String(n).padStart(2, '0'); };
        const a = document.createElement('a');
        a.download = 'mecam-' + nombre + '-' + t.getFullYear() + p(t.getMonth() + 1) + p(t.getDate()) +
                     '-' + p(t.getHours()) + p(t.getMinutes()) + p(t.getSeconds()) + '.jpg';
        a.href = URL.createObjectURL(b);
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
        aviso('Foto guardada');
      })
      .catch(function () { aviso('No se pudo capturar la foto'); });
  }

  // ---- Vista ampliada con zoom
  const visor = $('#visor');
  const fimg = $('#focoImg');

  function aplicarZoom() {
    fimg.style.transform = 'translate(' + foco.x + 'px, ' + foco.y + 'px) scale(' + foco.zoom + ')';
    visor.style.cursor = foco.zoom > 1 ? 'grab' : 'default';
    $('#fZoom').textContent = Math.round(foco.zoom * 100) + '%';
  }
  function limitar() {
    const r = visor.getBoundingClientRect();
    const mx = r.width * (foco.zoom - 1) / 2;
    const my = r.height * (foco.zoom - 1) / 2;
    foco.x = Math.max(-mx, Math.min(mx, foco.x));
    foco.y = Math.max(-my, Math.min(my, foco.y));
  }
  function zoomPor(f) {
    foco.zoom = Math.max(1, Math.min(8, foco.zoom * f));
    if (foco.zoom === 1) { foco.x = 0; foco.y = 0; }
    limitar();
    aplicarZoom();
  }
  function resetZoom() { foco.zoom = 1; foco.x = 0; foco.y = 0; aplicarZoom(); }

  const punteros = new Map();
  let distIni = 0, zoomIni = 1;
  function distancia() {
    const p = Array.from(punteros.values());
    return Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
  }
  visor.addEventListener('wheel', function (e) {
    e.preventDefault();
    zoomPor(e.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, { passive: false });
  visor.addEventListener('pointerdown', function (e) {
    visor.setPointerCapture(e.pointerId);
    punteros.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (punteros.size === 2) { distIni = distancia(); zoomIni = foco.zoom; }
    if (foco.zoom > 1) visor.style.cursor = 'grabbing';
  });
  visor.addEventListener('pointermove', function (e) {
    const p = punteros.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (punteros.size === 1 && foco.zoom > 1) {
      foco.x += dx; foco.y += dy;
      limitar(); aplicarZoom();
    } else if (punteros.size === 2 && distIni > 0) {
      foco.zoom = Math.max(1, Math.min(8, zoomIni * distancia() / distIni));
      if (foco.zoom === 1) { foco.x = 0; foco.y = 0; }
      limitar(); aplicarZoom();
    }
  });
  function soltar(e) {
    punteros.delete(e.pointerId);
    visor.style.cursor = foco.zoom > 1 ? 'grab' : 'default';
  }
  visor.addEventListener('pointerup', soltar);
  visor.addEventListener('pointercancel', soltar);
  visor.addEventListener('dblclick', function () {
    if (foco.zoom > 1) resetZoom(); else zoomPor(2.5);
  });

  function infoFoco(c) {
    const vivo = !!c.en_vivo;
    const e = $('#focoEstado');
    e.textContent = vivo ? 'EN VIVO' : 'SIN SEÑAL';
    e.className = 'estado ' + (vivo ? 'vivo' : 'sin');
    pintarChips($('#focoChips'), vivo ? c.conteo : {});
    pintarRecPill($('#focoRec'), c.rec);
  }

  function cargarFoco() {
    $('#focoNombre').textContent = foco.nombre;
    conectarImg(fimg, foco.nombre, true);
    const c = camaras.find(function (x) { return x.nombre === foco.nombre; });
    if (c) infoFoco(c);
  }

  let tirasClave = '';
  let tirasTimer = null;
  function armarTiras() {
    const clave = camaras.map(function (c) { return c.nombre; }).join('|') + '#' + foco.nombre;
    if (clave === tirasClave) return;
    tirasClave = clave;
    const cont = $('#tiras');
    cont.textContent = '';
    camaras.forEach(function (c) {
      const m = document.createElement('div');
      m.className = 'mini' + (c.nombre === foco.nombre ? ' activa' : '');
      m.dataset.cam = c.nombre;
      const im = document.createElement('img');
      im.alt = '';
      const sp = document.createElement('span');
      sp.textContent = c.nombre;
      m.append(im, sp);
      m.onclick = function () { cambiarFoco(c.nombre); };
      cont.appendChild(m);
    });
    refrescarTiras();
  }
  function refrescarTiras() {
    document.querySelectorAll('#tiras .mini').forEach(function (m) {
      m.firstChild.src = urlFoto(m.dataset.cam, 't=' + Date.now());
    });
  }

  function abrirFoco(nombre) {
    foco.nombre = nombre;
    resetZoom();
    $('#foco').hidden = false;
    tirasClave = '';
    cargarFoco();
    armarTiras();
    clearInterval(tirasTimer);
    tirasTimer = setInterval(refrescarTiras, 2000);
  }
  function cambiarFoco(nombre) {
    foco.nombre = nombre;
    resetZoom();
    tirasClave = '';
    cargarFoco();
    armarTiras();
  }
  function cerrarFoco() {
    clearInterval(tirasTimer);
    foco.nombre = null;
    fimg.onerror = null;
    fimg.src = '';
    $('#foco').hidden = true;
    if (document.fullscreenElement) { try { document.exitFullscreen(); } catch (e) {} }
  }
  function vecina(delta) {
    if (!camaras.length || !foco.nombre) return;
    let i = camaras.findIndex(function (c) { return c.nombre === foco.nombre; });
    i = (i + delta + camaras.length) % camaras.length;
    cambiarFoco(camaras[i].nombre);
  }
  function pantallaCompleta(el) {
    try {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (el.requestFullscreen) el.requestFullscreen();
      else aviso('Este navegador no permite pantalla completa');
    } catch (e) {}
  }

  // ---- Botones
  $('#fCerrar').onclick = cerrarFoco;
  $('#fPrev').onclick = function () { vecina(-1); };
  $('#fNext').onclick = function () { vecina(1); };
  $('#fMas').onclick = function () { zoomPor(1.4); };
  $('#fMenos').onclick = function () { zoomPor(1 / 1.4); };
  $('#fReset').onclick = resetZoom;
  $('#fFoto').onclick = function () { if (foco.nombre) capturar(foco.nombre); };
  $('#fPant').onclick = function () { pantallaCompleta($('#foco')); };
  $('#bPantalla').onclick = function () { pantallaCompleta(document.documentElement); };
  function alternarActividad(abrir) {
    const panel = $('#actividad');
    const abierto = abrir === undefined ? !panel.classList.contains('abierto') : abrir;
    panel.classList.toggle('abierto', abierto);
    $('#bAct').classList.toggle('on', abierto);
    if (abierto) { eventosVistos = eventosPrev; $('#badgeAct').style.display = 'none'; }
  }
  $('#bAct').onclick = function () { alternarActividad(); };
  $('#aCerrar').onclick = function () { alternarActividad(false); };
  // ---- Grabación de clips: interruptor general (botón de la barra) y selector por cámara (indicador REC)
  function pintarRec() {
    const b = $('#bRec');
    b.classList.toggle('rec-on', grabacionActiva);
    b.setAttribute('aria-pressed', String(grabacionActiva));
    b.dataset.tip = grabacionActiva ? 'Grabación de clips: activada (Q)' : 'Grabación de clips: desactivada (Q)';
    cambiarIcono(b, grabacionActiva ? 'rec' : 'rec_off');
  }
  function ponerGrabacion(cuerpo, mensaje) {
    return fetch('/api/grabacion', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) })
      .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
      .then(function (d) { grabacionActiva = d.activo; pintarRec(); aviso(mensaje(d)); return d; })
      .catch(function () { aviso('No se pudo cambiar la grabación'); });
  }
  function alternarRecCamara(nombre) {
    if (!grabacionActiva) { aviso('La grabación de clips está desactivada: actívala con el botón de la barra'); return; }
    const c = camaras.find(function (x) { return x.nombre === nombre; });
    const quiere = !c || c.rec === 'excluida';
    ponerGrabacion({ camara: nombre, activo: quiere }, function () {
      return quiere ? nombre + ': grabará clips' : nombre + ': ya no grabará clips';
    }).then(function () {
      if (!c) return;
      c.rec = quiere ? 'lista' : 'excluida';
      const t = tiles.get(nombre);
      if (t) actualizarTile(t, c);
      if (foco.nombre === nombre) infoFoco(c);
    });
  }
  $('#bRec').onclick = function () {
    ponerGrabacion({ activo: !grabacionActiva }, function (d) { return d.activo ? 'Grabación de clips activada' : 'Grabación de clips desactivada'; });
  };
  $('#focoRec').onclick = function () { if (foco.nombre) alternarRecCamara(foco.nombre); };
  function iconosPantalla() {
    const n = document.fullscreenElement ? 'reducir' : 'ampliar';
    cambiarIcono($('#bPantalla'), n);
    cambiarIcono($('#fPant'), n);
  }
  document.addEventListener('fullscreenchange', iconosPantalla);
  if (!document.fullscreenEnabled) { $('#bPantalla').style.display = 'none'; $('#fPant').style.display = 'none'; }

  const ORDEN_COLS = ['auto', '1', '2', '3'];
  function pintarPrefs() {
    $('#valLayout').textContent = prefs.cols === 'auto' ? 'A' : String(prefs.cols);
    $('#bLayout').classList.toggle('on', prefs.cols !== 'auto');
    $('#bRaw').classList.toggle('on', prefs.raw);
    $('#bSonido').classList.toggle('on', prefs.sonido);
    $('#bRaw').setAttribute('aria-pressed', String(prefs.raw));
    $('#bSonido').setAttribute('aria-pressed', String(prefs.sonido));
    cambiarIcono($('#bSonido'), prefs.sonido ? 'campana' : 'campana_off');
  }
  function siguienteLayout() {
    const i = ORDEN_COLS.indexOf(String(prefs.cols));
    prefs.cols = ORDEN_COLS[(i + 1) % ORDEN_COLS.length];
    guardar(); pintarPrefs(); layout();
    aviso(prefs.cols === 'auto' ? 'Distribución automática' : prefs.cols + (prefs.cols === '1' ? ' columna' : ' columnas'));
  }
  $('#bLayout').onclick = siguienteLayout;
  $('#bRaw').onclick = function () {
    prefs.raw = !prefs.raw; guardar(); pintarPrefs(); recargarStreams();
    aviso(prefs.raw ? 'Mostrando el video sin recuadros' : 'Mostrando las detecciones');
  };
  $('#bSonido').onclick = function () {
    prefs.sonido = !prefs.sonido; guardar(); pintarPrefs();
    if (prefs.sonido) { pitido(); aviso('Sonará un aviso cuando aparezca una persona'); }
    else aviso('Alerta sonora desactivada');
  };

  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const ampliada = !$('#foco').hidden;
    if (e.key === 'Escape') {
      if (ampliada) cerrarFoco(); else alternarActividad(false);
    } else if (ampliada) {
      if (e.key === 'ArrowLeft') vecina(-1);
      else if (e.key === 'ArrowRight') vecina(1);
      else if (e.key === '+' || e.key === '=') zoomPor(1.4);
      else if (e.key === '-') zoomPor(1 / 1.4);
      else if (e.key === '0') resetZoom();
      else if (e.key === 'f' || e.key === 'F') pantallaCompleta($('#foco'));
      else if (e.key === 'c' || e.key === 'C') { if (foco.nombre) capturar(foco.nombre); }
    } else {
      const k = e.key.toLowerCase();
      if (k === 'a') alternarActividad();
      else if (k === 's') $('#bSonido').click();
      else if (k === 'r') $('#bRaw').click();
      else if (k === 'l') siguienteLayout();
      else if (k === 'f') pantallaCompleta(document.documentElement);
      else if (k === 'g') location.href = '/grabaciones';
      else if (k === 'q') $('#bRec').click();
    }
  });
  window.addEventListener('resize', layout);

  // ---- Reloj
  function reloj() {
    $('#reloj').textContent = new Date().toLocaleString('es-ES', {
      weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  }
  reloj();
  setInterval(reloj, 1000);

  pintarPrefs();
  layout();
  sondear();
})();
</script>
</body></html>
"""


# ---------------------------------------------------------------- Vinculación por QR
_ESTILO = ("body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
           "background:#0a0e13;color:#e8eef6;font-family:system-ui,sans-serif;text-align:center}"
           "div{max-width:420px;padding:24px}h1{font-size:22px}p{color:#8fa3bb;line-height:1.5}")


def _pagina_simple(titulo, texto):
    return ("<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>MeCam</title>"
            f"<style>{_ESTILO}</style></head><body><div><h1>{titulo}</h1><p>{texto}</p></div></body></html>")


PAGINA_SIN_VINCULO = _pagina_simple(
    "Este dispositivo no está vinculado",
    "En la computadora abre <b>MeCam</b>, toca <b>Vincular dispositivo</b> y escanea el QR "
    "con la cámara de este celular.")
PAGINA_CODIGO_USADO = _pagina_simple(
    "Este código ya no sirve",
    "Cada QR se puede usar una sola vez y vence a los pocos minutos. "
    "En la computadora toca <b>Vincular dispositivo</b> para generar uno nuevo.")


@web.middleware
async def autorizar(request, handler):
    """Cuando hay dispositivos vinculados, solo entran ellos (y esta computadora / tu red Tailscale)."""
    ruta = request.path
    if ruta.startswith("/v/") or ruta == "/api/vincular":
        return await handler(request)          # validan su propio código de un solo uso
    if not registro.proteccion:
        return await handler(request)          # todavía no hay nada vinculado: acceso abierto, como antes
    if vinculos.es_confiable(request.remote):
        return await handler(request)
    disp = registro.verificar(vinculos.credencial(request)) if request.secure else None
    if disp is not None:
        request["disp"] = disp
        return await handler(request)
    if ruta.startswith("/ws/") or request.method != "GET":
        raise web.HTTPUnauthorized(text="dispositivo no vinculado")
    return web.Response(status=403, text=PAGINA_SIN_VINCULO, content_type="text/html")


async def api_vincular(request):
    """La app MeCam canjea aquí el código del QR y recibe su credencial propia."""
    if not request.secure:
        raise web.HTTPForbidden(text="usa HTTPS")
    try:
        datos = await request.json()
    except Exception:
        raise web.HTTPBadRequest()
    if not registro.canjear_token(str(datos.get("token", ""))):
        await asyncio.sleep(1)
        raise web.HTTPForbidden(text="codigo invalido o vencido")
    disp_id, secreto, nombre = registro.vincular("camara", str(datos.get("modelo", "")))
    evento(f"{nombre}: cámara vinculada")
    print(f"[*] Dispositivo vinculado: {nombre} (cámara)")
    return web.json_response({"id": disp_id, "secreto": secreto, "nombre": nombre})


async def vinculo_navegador(request):
    """Quien escanea el QR con la cámara del celular llega aquí y queda vinculado como visor."""
    if not request.secure:
        raise web.HTTPFound(f"https://{request.url.host}:{PORT}{request.path_qs}")
    if not registro.canjear_token(request.match_info["token"]):
        await asyncio.sleep(1)
        return web.Response(status=410, text=PAGINA_CODIGO_USADO, content_type="text/html")
    disp_id, secreto, nombre = registro.vincular("visor", request.headers.get("User-Agent", ""))
    evento(f"{nombre}: visor vinculado")
    print(f"[*] Dispositivo vinculado: {nombre} (visor)")
    resp = web.HTTPFound("/ver")
    resp.set_cookie("mecam", f"{disp_id}.{secreto}", max_age=10 * 365 * 24 * 3600,
                    secure=True, httponly=True, samesite="Lax", path="/")
    raise resp


async def refresco_tailscale():
    loop = asyncio.get_running_loop()
    while True:
        await loop.run_in_executor(None, vinculos.refrescar_tailscale)
        await asyncio.sleep(60)


# ---------------------------------------------------------------- Procesamiento
def procesar(model, datos):
    """Recibe un JPEG, detecta y sigue objetos. Devuelve (JPEG con recuadros, conteo, resolución)."""
    img = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    r = model.track(
        img, persist=True, classes=CLASES,
        tracker="bytetrack.yaml", verbose=False,
    )[0]
    conteo = {}
    if r.boxes is not None and r.boxes.cls is not None:
        for c in r.boxes.cls.tolist():
            en = r.names[int(c)]
            plural = NOMBRES.get(en, (en, en))[1]
            conteo[plural] = conteo.get(plural, 0) + 1
    ok, buf = cv2.imencode(".jpg", r.plot())
    alto, ancho = img.shape[:2]
    return (buf.tobytes() if ok else None), conteo, f"{ancho}x{alto}"


def estado_rec(nombre):
    """Qué muestra el indicador REC de una cámara: grabando / lista / excluida / off."""
    if not grabador.activo:
        return "off"
    if nombre in grabador.excluidas:
        return "excluida"
    return "grabando" if grabador.grabando(nombre) else "lista"


def registrar_detecciones(cam, conteo, ahora):
    """Anota en la actividad cuando aparece algo nuevo (con un descanso para no repetir)."""
    for etiqueta, cantidad in conteo.items():
        if cantidad > 0 and cam.previo.get(etiqueta, 0) == 0:
            if ahora - cam.ultima_alerta.get(etiqueta, 0) > 15:
                cam.ultima_alerta[etiqueta] = ahora
                evento(f"{cam.nombre}: detección de {SINGULAR.get(etiqueta, etiqueta)}")
    cam.previo = dict(conteo)


# ---------------------------------------------------------------- Rutas web
async def pagina_camara(request):
    return web.Response(text=PAGINA_CAMARA, content_type="text/html")


async def pagina_ver(request):
    return web.Response(text=PAGINA_VER.replace("<!--SPRITE-->", iconos.SPRITE), content_type="text/html",
                        headers={"Cache-Control": "no-store"})


async def estado(request):
    ahora = time.time()
    lista = []
    for c in camaras.values():
        hace = (ahora - c.ultimo) if c.ultimo else None
        lista.append({
            "nombre": c.nombre,
            "en_vivo": hace is not None and hace < SEGS_EN_VIVO,
            "hace": round(hace, 1) if hace is not None else None,
            "fps": round(c.fps, 1),
            "res": c.res,
            "conteo": c.conteo,
            "conectada_hace": int(ahora - c.desde),
            "rec": estado_rec(c.nombre),
        })
    total = eventos[0]["id"] if eventos else 0
    return web.json_response(
        {"ip": IP_LOCAL, "grabacion": grabador.activo, "camaras": lista, "eventos": list(eventos)[:40], "total_eventos": total},
        headers={"Cache-Control": "no-store"},
    )


async def foto(request):
    cam = camaras.get(request.match_info["cam"])
    if cam is None or not cam.jpg:
        raise web.HTTPNotFound()
    datos = cam.crudo if request.query.get("raw") == "1" else cam.jpg
    return web.Response(body=datos, content_type="image/jpeg", headers={"Cache-Control": "no-store"})


async def stream(request):
    nombre = request.match_info["cam"]
    crudo = request.query.get("raw") == "1"
    resp = web.StreamResponse(headers={
        "Content-Type": "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-store",
    })
    await resp.prepare(request)
    ultimo_n = -1
    ausente_desde = None
    try:
        while not parando:
            cam = camaras.get(nombre)
            if cam is None:
                # el celular se desconectó (o se está reconectando): se espera un momento antes de cortar
                if ausente_desde is None:
                    ausente_desde = time.time()
                elif time.time() - ausente_desde > 8:
                    break
                await asyncio.sleep(0.2)
                continue
            ausente_desde = None
            if cam.n != ultimo_n and cam.jpg:
                ultimo_n = cam.n
                datos = cam.crudo if crudo else cam.jpg
                await resp.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(datos)
                    + datos + b"\r\n"
                )
            await asyncio.sleep(0.03)
    except Exception:
        pass
    return resp


async def pagina_grabaciones(request):
    return web.Response(text=grabaciones.PAGINA.replace("<!--SPRITE-->", iconos.SPRITE), content_type="text/html",
                        headers={"Cache-Control": "no-store"})


async def api_grabaciones(request):
    datos = grabador.resumen()
    datos["clips"] = grabador.listar()
    return web.json_response(datos, headers={"Cache-Control": "no-store"})


async def api_grabacion(request):
    """Interruptor de la grabación: general ({"activo": true}) o de una cámara ({"camara": "Entrada", "activo": false})."""
    try:
        datos = await request.json()
    except Exception:
        raise web.HTTPBadRequest()
    activo = bool(datos.get("activo"))
    camara = datos.get("camara")
    if camara is None:
        grabador.set_activo(activo)
        evento("Grabación de clips " + ("activada" if activo else "desactivada"))
    else:
        grabador.set_camara(str(camara)[:40], activo)
        evento(f"{camara}: " + ("grabará clips" if activo else "ya no grabará clips"))
    return web.json_response({"activo": grabador.activo, "excluidas": sorted(grabador.excluidas)})


async def api_borrar(request):
    if not grabador.borrar(request.match_info["id"]):
        raise web.HTTPNotFound()
    return web.json_response({"ok": True})


async def miniatura(request):
    ruta = grabador.ruta_miniatura(request.match_info["id"])
    if not ruta:
        raise web.HTTPNotFound()
    return web.FileResponse(ruta, headers={"Cache-Control": "max-age=3600"})


async def archivo(request):
    ruta = grabador.ruta_video(request.match_info["id"])
    if not ruta:
        raise web.HTTPNotFound()
    return web.FileResponse(ruta, headers={"Content-Disposition": f'attachment; filename="{os.path.basename(ruta)}"'})


async def clip(request):
    """Reproduce una grabación como video en directo (sirve en cualquier navegador, sin códecs)."""
    ruta = grabador.ruta_video(request.match_info["id"])
    if not ruta:
        raise web.HTTPNotFound()
    resp = web.StreamResponse(headers={
        "Content-Type": "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-store",
    })
    await resp.prepare(request)
    loop = asyncio.get_running_loop()
    cap = cv2.VideoCapture(ruta)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    try:
        while not parando:
            ok, img = await loop.run_in_executor(None, cap.read)
            if not ok:
                break
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                continue
            datos = buf.tobytes()
            await resp.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(datos)
                             + datos + b"\r\n")
            await asyncio.sleep(1 / max(fps, 1))
    except Exception:
        pass
    finally:
        cap.release()
    return resp


async def ws_camara(request):
    pedido = limpiar_nombre(request.match_info["cam"])
    disp_id = request.query.get("id", "")[:64]
    disp = request.get("disp")
    if disp is not None and disp["tipo"] == "camara":
        pedido, disp_id = limpiar_nombre(disp["nombre"]), disp["id"]   # nombre e identidad los decide el servidor
    # heartbeat: si un celular se apaga o pierde el Wi-Fi, se detecta y se desconecta solo
    ws = web.WebSocketResponse(max_msg_size=10 * 1024 * 1024, heartbeat=15)
    await ws.prepare(request)
    loop = asyncio.get_running_loop()

    # Nunca dos cámaras con el mismo nombre
    nombre = pedido
    viejo = camaras.get(nombre)
    if viejo is not None:
        if disp_id and viejo.id == disp_id:
            await viejo.cerrar()      # es el mismo celular reconectando: reemplaza la conexión vieja
        else:
            n = 2
            while f"{pedido}-{n}" in camaras:
                n += 1
            nombre = f"{pedido}-{n}"
            evento(f"El nombre «{pedido}» ya estaba en uso: esta cámara se llama «{nombre}»")

    cam = Camara(nombre, disp_id, ws)
    camaras[nombre] = cam
    evento(f"{nombre}: cámara conectada")
    print(f"[+] Cámara conectada: {nombre}")
    try:
        await ws.send_str("nombre:" + nombre)   # el celular muestra el nombre que se le asignó
        model = await loop.run_in_executor(None, YOLO, MODELO)
        async for msg in ws:
            if msg.type == web.WSMsgType.BINARY:
                res = await loop.run_in_executor(None, procesar, model, msg.data)
                if res and res[0]:
                    jpg, conteo, resolucion = res
                    ahora = time.time()
                    if cam.ultimo:
                        dt = ahora - cam.ultimo
                        if dt > 0:
                            cam.fps = 0.8 * cam.fps + 0.2 / dt if cam.fps else 1 / dt
                    cam.ultimo = ahora
                    cam.jpg, cam.crudo = jpg, msg.data
                    cam.conteo, cam.res = conteo, resolucion
                    cam.n = next(_id_cuadro)
                    registrar_detecciones(cam, conteo, ahora)
                    grabador.agregar(nombre, jpg, conteo, ahora)
                await ws.send_str("ok")
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        grabador.cerrar_camara(nombre)         # guarda el clip que estuviera grabándose
        if camaras.get(nombre) is cam:        # no borrar a un reemplazo que ya tomó este nombre
            del camaras[nombre]
            evento(f"{nombre}: cámara desconectada")
            print(f"[-] Cámara desconectada: {nombre}")
    return ws


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


async def iniciar(ctx, ip, parar=None, al_arrancar=None):
    """Levanta el servidor. Sin 'parar' corre hasta Ctrl+C; con 'parar' termina cuando se activa."""
    global IP_LOCAL, parando
    IP_LOCAL = ip
    parando = False
    app = web.Application(middlewares=[autorizar])
    app.add_routes([
        web.get("/v/{token}", vinculo_navegador),
        web.post("/api/vincular", api_vincular),
        web.get("/", pagina_camara),
        web.get("/ver", pagina_ver),
        web.get("/estado", estado),
        web.get("/foto/{cam}", foto),
        web.get("/ws/{cam}", ws_camara),
        web.get("/stream/{cam}", stream),
        web.get("/grabaciones", pagina_grabaciones),
        web.get("/api/grabaciones", api_grabaciones),
        web.delete("/api/grabaciones/{id}", api_borrar),
        web.post("/api/grabacion", api_grabacion),
        web.get("/miniatura/{id}", miniatura),
        web.get("/clip/{id}", clip),
        web.get("/archivo/{id}", archivo),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    tarea_ts = None
    try:
        tarea_ts = asyncio.create_task(refresco_tailscale())
        await web.TCPSite(runner, "0.0.0.0", PORT, ssl_context=ctx).start()
        await web.TCPSite(runner, "0.0.0.0", PORT_HTTP).start()
        print("=" * 50)
        print("MeCam")
        print(f"Centro de control:         https://localhost:{PORT}/ver")
        print(f"IP de esta computadora:    {ip}")
        print("Para vincular un celular usa el boton 'Vincular dispositivo' de la ventana de MeCam.")
        print("=" * 50)
        if al_arrancar:
            al_arrancar()
        if parar is None:
            while True:
                await asyncio.sleep(1)
        else:
            await parar.wait()
    finally:
        if tarea_ts is not None:
            tarea_ts.cancel()
        parando = True
        for c in list(camaras.values()):
            await c.cerrar()
        camaras.clear()
        await asyncio.get_running_loop().run_in_executor(None, grabador.cerrar_todo)   # termina de guardar
        try:
            await asyncio.wait_for(runner.cleanup(), 8)
        except Exception:
            pass


class Servidor:
    """Arranca y detiene el servidor en segundo plano (lo usa la ventana de MeCam)."""

    def __init__(self):
        self.hilo = None
        self.loop = None
        self.parar = None
        self.listo = threading.Event()
        self.error = None
        self.ip = ""
        self.huella = ""
        self.corriendo = False

    def nuevo_qr(self):
        """Código de un solo uso y la dirección que va dentro del QR."""
        token = registro.nuevo_token()
        return token, f"https://{self.ip}:{PORT}/v/{token}#fp={self.huella}"

    def desvincular(self, disp_id):
        """Quita el dispositivo y corta su conexión si estaba transmitiendo."""
        registro.desvincular(disp_id)
        if self.loop is not None:
            for c in list(camaras.values()):
                if c.id == disp_id:
                    asyncio.run_coroutine_threadsafe(c.cerrar(), self.loop)

    def iniciar(self):
        """Arranca el servidor. Devuelve True si quedó funcionando."""
        if self.corriendo:
            return True
        self.error = None
        self.listo.clear()
        self.hilo = threading.Thread(target=self._hilo, daemon=True)
        self.hilo.start()
        self.listo.wait()
        return self.error is None and self.corriendo

    def detener(self):
        if self.loop is not None and self.parar is not None:
            try:
                self.loop.call_soon_threadsafe(self.parar.set)
            except RuntimeError:
                pass
        if self.hilo is not None:
            self.hilo.join(timeout=15)
        self.corriendo = False

    def _hilo(self):
        try:
            asyncio.run(self._main())
        except Exception as e:
            self.error = e
            print(f"[!] Error del servidor: {e}")
        finally:
            self.corriendo = False
            self.listo.set()

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        self.parar = asyncio.Event()
        self.ip = ip_local()
        print("Cargando el modelo de detección (la primera vez se descarga y puede tardar)...")
        await self.loop.run_in_executor(None, YOLO, MODELO)
        ruta_cert, ruta_clave, self.huella = vinculos.asegurar_certificado(self.ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(ruta_cert, ruta_clave)

        def listo():
            self.corriendo = True
            self.listo.set()

        await iniciar(ctx, self.ip, self.parar, listo)


def main():
    ip = ip_local()
    ruta_cert, ruta_clave, _ = vinculos.asegurar_certificado(ip)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(ruta_cert, ruta_clave)
    try:
        asyncio.run(iniciar(ctx, ip))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
