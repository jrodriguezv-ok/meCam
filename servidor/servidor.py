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
svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* ---------- Barra superior ---------- */
#barra{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  padding:10px 16px;padding-top:calc(10px + env(safe-area-inset-top,0px));
  background:rgba(17,24,35,.85);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--borde);
}
.logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px;letter-spacing:.3px}
.logo i{width:12px;height:12px;border-radius:50%;background:var(--acento);box-shadow:0 0 14px var(--acento)}
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
.estado.sin{color:var(--aviso)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{font-size:12px;padding:3px 9px;border-radius:999px;background:rgba(248,113,113,.2);border:1px solid rgba(248,113,113,.55);color:#ffd9d9}
.chip.auto{background:rgba(56,189,248,.18);border-color:rgba(56,189,248,.55);color:#d3efff}
.meta{margin-left:auto;font-size:11.5px;color:#cbd5e1;font-variant-numeric:tabular-nums;text-shadow:0 1px 3px #000}
.acciones{position:absolute;top:8px;right:8px;display:flex;gap:6px;opacity:0;transition:opacity .15s}
.tile:hover .acciones,.tile:focus-within .acciones{opacity:1}
@media (hover:none){.acciones{opacity:1}}
.ic{
  width:34px;height:34px;display:grid;place-items:center;border-radius:9px;
  border:1px solid #ffffff2b;background:#0009;backdrop-filter:blur(6px);color:var(--texto);
}
.ic:hover{border-color:var(--acento);color:var(--acento)}
.ic svg{width:18px;height:18px}

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
#foco{position:fixed;inset:0;z-index:30;background:rgba(4,7,11,.97);display:flex;flex-direction:column}
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

/* ---------- Aviso emergente ---------- */
#toast{
  position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);background:var(--panel2);
  border:1px solid var(--borde);padding:10px 16px;border-radius:12px;opacity:0;transition:.25s;
  z-index:60;pointer-events:none;font-size:14px;box-shadow:0 10px 30px #0008;
}
#toast.ver{opacity:1;transform:translateX(-50%)}

@media (max-width:700px){
  #barra{gap:8px;padding:8px 12px}
  .logo small,.btn span{display:none}
  .btn{padding:8px 10px}
  #reloj{display:none}
  .mini{width:104px;height:64px}
}
</style></head><body>

<header id="barra">
  <div class="logo"><i></i><span>MeCam</span><small>Centro de control</small></div>
  <span class="pill" id="pSrv"><span class="punto"></span><b id="pSrvTxt">Conectando…</b></span>
  <span class="pill"><b id="nCams">0</b> cámaras · <b id="nVivo">0</b> en vivo</span>
  <span class="pill" id="reloj"></span>
  <span class="espacio"></span>
  <div class="grupo" id="gLayout" role="group" aria-label="Columnas de la cuadrícula">
    <button data-c="auto" title="Distribución automática">Auto</button>
    <button data-c="1" title="1 columna">1</button>
    <button data-c="2" title="2 columnas">2</button>
    <button data-c="3" title="3 columnas">3</button>
  </div>
  <button class="btn" id="bRaw" data-i="recuadro" title="Ver el video sin los recuadros de detección" aria-label="Ver sin recuadros"><span>Sin recuadros</span></button>
  <button class="btn" id="bSonido" data-i="campana" title="Avisar con un sonido cuando aparezca una persona" aria-label="Alerta sonora"><span>Alerta sonora</span></button>
  <button class="btn" id="bAct" data-i="actividad" title="Registro de actividad" aria-label="Actividad"><span>Actividad</span></button>
  <button class="btn" id="bPantalla" data-i="ampliar" title="Pantalla completa" aria-label="Pantalla completa"><span>Pantalla completa</span></button>
</header>

<main id="grid"></main>

<div id="vacio">
  <div class="caja">
    <h2>Esperando cámaras…</h2>
    <p>Abre la app <b>MeCam</b> en tus celulares y escribe esta IP:</p>
    <p><code id="vacioIp">—</code></p>
    <p>Cada celular debe tener un nombre distinto. Aparecerán aquí solos.</p>
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
    <span class="espacio"></span>
    <button class="ic" id="fPrev" data-i="izq" title="Cámara anterior" aria-label="Cámara anterior"></button>
    <button class="ic" id="fNext" data-i="der" title="Cámara siguiente" aria-label="Cámara siguiente"></button>
    <button class="ic" id="fMenos" data-i="menos" title="Alejar" aria-label="Alejar"></button>
    <span class="pill" id="fZoom">100%</span>
    <button class="ic" id="fMas" data-i="mas" title="Acercar" aria-label="Acercar"></button>
    <button class="ic" id="fReset" data-i="reset" title="Restablecer zoom" aria-label="Restablecer zoom"></button>
    <button class="ic" id="fFoto" data-i="camara" title="Capturar foto" aria-label="Capturar foto"></button>
    <button class="ic" id="fPant" data-i="ampliar" title="Pantalla completa" aria-label="Pantalla completa"></button>
  </div>
  <div id="visor"><img id="focoImg" alt="" draggable="false"></div>
  <div id="tiras"></div>
</div>

<div id="toast" role="status"></div>

<script>
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);

  const ICONOS = {
    camara: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    ampliar: '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>',
    cerrar: '<path d="M18 6 6 18M6 6l12 12"/>',
    mas: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35M11 8v6M8 11h6"/>',
    menos: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35M8 11h6"/>',
    reset: '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>',
    campana: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>',
    recuadro: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/>',
    actividad: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    izq: '<path d="m15 18-6-6 6-6"/>',
    der: '<path d="m9 18 6-6-6-6"/>'
  };
  const SING = { personas: 'persona', autos: 'auto', motos: 'moto', buses: 'bus', camiones: 'camión',
                 bicicletas: 'bicicleta', gatos: 'gato', perros: 'perro' };
  function svg(n) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONOS[n] || '') + '</svg>'; }
  document.querySelectorAll('[data-i]').forEach(function (e) { e.insertAdjacentHTML('afterbegin', svg(e.dataset.i)); });

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
    img.src = urlStream(nombre);
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
      s.textContent = v + ' ' + (v === 1 ? (SING[k] || k) : k);
      cont.appendChild(s);
    });
  }

  // ---- Cada cámara es una "ficha" de la cuadrícula
  function crearTile(nombre) {
    const el = document.createElement('div');
    el.className = 'tile';
    el.tabIndex = 0;
    el.innerHTML =
      '<img class="video" alt="">' +
      '<div class="arriba"><span class="nombre"></span><span class="estado sin">SIN SEÑAL</span></div>' +
      '<div class="acciones">' +
        '<button class="ic" data-a="foto" title="Capturar foto" aria-label="Capturar foto">' + svg('camara') + '</button>' +
        '<button class="ic" data-a="ampliar" title="Ampliar" aria-label="Ampliar">' + svg('ampliar') + '</button>' +
      '</div>' +
      '<div class="abajo"><span class="chips"></span><span class="meta"></span></div>';
    const t = {
      el: el, nombre: nombre,
      img: el.querySelector('img'), nom: el.querySelector('.nombre'), est: el.querySelector('.estado'),
      chips: el.querySelector('.chips'), meta: el.querySelector('.meta'), personas: false
    };
    t.nom.textContent = nombre;
    t.img.alt = 'Cámara ' + nombre;
    el.addEventListener('click', function (e) {
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
      const s = document.createElement('span');
      s.textContent = e.texto;
      fila.append(h, s);
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
  $('#bAct').onclick = function () { $('#actividad').classList.toggle('abierto'); };
  $('#aCerrar').onclick = function () { $('#actividad').classList.remove('abierto'); };

  function pintarPrefs() {
    document.querySelectorAll('#gLayout button').forEach(function (b) {
      b.classList.toggle('on', b.dataset.c === String(prefs.cols));
    });
    $('#bRaw').classList.toggle('on', prefs.raw);
    $('#bSonido').classList.toggle('on', prefs.sonido);
  }
  document.querySelectorAll('#gLayout button').forEach(function (b) {
    b.onclick = function () { prefs.cols = b.dataset.c; guardar(); pintarPrefs(); layout(); };
  });
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
    if (e.key === 'Escape') {
      if (!$('#foco').hidden) cerrarFoco();
      else $('#actividad').classList.remove('abierto');
    } else if (!$('#foco').hidden) {
      if (e.key === 'ArrowLeft') vecina(-1);
      else if (e.key === 'ArrowRight') vecina(1);
      else if (e.key === '+' || e.key === '=') zoomPor(1.4);
      else if (e.key === '-') zoomPor(1 / 1.4);
      else if (e.key === '0') resetZoom();
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
    return web.Response(text=PAGINA_VER, content_type="text/html")


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
        })
    total = eventos[0]["id"] if eventos else 0
    return web.json_response(
        {"ip": IP_LOCAL, "camaras": lista, "eventos": list(eventos)[:40], "total_eventos": total},
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


async def ws_camara(request):
    pedido = limpiar_nombre(request.match_info["cam"])
    disp_id = request.query.get("id", "")[:64]
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
                await ws.send_str("ok")
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
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


def crear_certificado(ip):
    """El navegador del celular exige HTTPS para dar acceso a la cámara. Creamos un certificado propio."""
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


async def iniciar(ctx, ip, parar=None, al_arrancar=None):
    """Levanta el servidor. Sin 'parar' corre hasta Ctrl+C; con 'parar' termina cuando se activa."""
    global IP_LOCAL, parando
    IP_LOCAL = ip
    parando = False
    app = web.Application()
    app.add_routes([
        web.get("/", pagina_camara),
        web.get("/ver", pagina_ver),
        web.get("/estado", estado),
        web.get("/foto/{cam}", foto),
        web.get("/ws/{cam}", ws_camara),
        web.get("/stream/{cam}", stream),
    ])
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        await web.TCPSite(runner, "0.0.0.0", PORT, ssl_context=ctx).start()
        await web.TCPSite(runner, "0.0.0.0", PORT_HTTP).start()
        print("=" * 50)
        print("MeCam")
        print(f"En el CELULAR (navegador): https://{ip}:{PORT}")
        print(f"En la APP de Android, IP:  {ip}")
        print(f"Centro de control:         https://localhost:{PORT}/ver")
        print("=" * 50)
        if al_arrancar:
            al_arrancar()
        if parar is None:
            while True:
                await asyncio.sleep(1)
        else:
            await parar.wait()
    finally:
        parando = True
        for c in list(camaras.values()):
            await c.cerrar()
        camaras.clear()
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
        self.corriendo = False

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
        ruta_cert, ruta_clave = crear_certificado(self.ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(ruta_cert, ruta_clave)

        def listo():
            self.corriendo = True
            self.listo.set()

        await iniciar(ctx, self.ip, self.parar, listo)


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
