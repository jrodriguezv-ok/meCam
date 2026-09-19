"""
MeCam - grabación de clips cuando se detecta una persona.

- Guarda un clip corto con recuadros (unos segundos ANTES y DESPUES de la detección).
- Los clips van a una carpeta de MeCam; se borran solos los más viejos (por antigüedad y por espacio).
- Página /grabaciones para verlos, descargarlos y borrarlos.
"""
import collections
import json
import os
import queue
import re
import threading
import time
import traceback

import cv2
import numpy as np

import vinculos

PRE_SEG = 3.0          # segundos anteriores a la detección que se incluyen en el clip
POST_SEG = 6.0         # segundos que sigue grabando después de la última detección
MAX_SEG = 90.0         # duración máxima de un clip
CUADROS_MIN = 2        # cuadros seguidos con una persona para empezar (evita falsas alarmas de un cuadro)
LIMITE_GB = 5.0        # al pasar este espacio se borran los clips más antiguos
DIAS_MAX = 30          # los clips más viejos que esto se borran
ETIQUETA = "personas"  # lo que dispara la grabación (clave del conteo)


def _limpio(nombre):
    """Nombre seguro para usar en archivos."""
    return re.sub(r"[^\w\- ]", "_", nombre).strip()[:40] or "camara"


def carpeta_grabaciones():
    ruta = os.environ.get("MECAM_GRABACIONES") or os.path.join(vinculos.carpeta_datos(), "grabaciones")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def _ruta_config():
    return os.path.join(vinculos.carpeta_datos(), "config.json")


def leer_config():
    try:
        with open(_ruta_config(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_config(cambios):
    datos = leer_config()
    datos.update(cambios)
    with open(_ruta_config(), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)


class _Sesion:
    def __init__(self, camara, frames, i_miniatura, ahora):
        self.camara = camara
        self.frames = frames              # [(instante, jpg)]
        self.i_miniatura = i_miniatura    # cuadro donde apareció la persona
        self.ultima_det = ahora


class Grabador:
    def __init__(self, carpeta=None, al_guardar=None):
        self.carpeta = carpeta or carpeta_grabaciones()
        os.makedirs(self.carpeta, exist_ok=True)
        self.activo = bool(leer_config().get("grabar", True))
        self.al_guardar = al_guardar          # función(texto) para anotar en la actividad
        self.buffers = {}                     # cámara -> cuadros recientes (antes de detectar)
        self.seguidos = {}                    # cámara -> cuadros seguidos con persona
        self.sesiones = {}                    # cámara -> clip en curso
        self.cola = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._trabajo, daemon=True).start()

    # ---------------------------------------------------------------- Entrada de cuadros
    def set_activo(self, valor):
        with self.lock:
            self.activo = bool(valor)
            if not self.activo:
                for s in self.sesiones.values():
                    self.cola.put(s)
                self.sesiones.clear()
        guardar_config({"grabar": self.activo})

    def agregar(self, camara, jpg, conteo, ahora=None):
        """Recibe cada cuadro procesado (con recuadros) y decide si hay que grabar."""
        ahora = time.time() if ahora is None else ahora
        hay = conteo.get(ETIQUETA, 0) > 0
        with self.lock:
            s = self.sesiones.get(camara)
            if s is None:
                buf = self.buffers.setdefault(camara, collections.deque())
                buf.append((ahora, jpg))
                while buf and ahora - buf[0][0] > PRE_SEG:
                    buf.popleft()
                if not self.activo:
                    self.seguidos[camara] = 0
                    return
                self.seguidos[camara] = self.seguidos.get(camara, 0) + 1 if hay else 0
                if self.seguidos[camara] >= CUADROS_MIN:
                    frames = list(buf)
                    self.sesiones[camara] = _Sesion(camara, frames, len(frames) - CUADROS_MIN, ahora)
                    buf.clear()
                    self.seguidos[camara] = 0
                return
            s.frames.append((ahora, jpg))
            if hay:
                s.ultima_det = ahora
            if ahora - s.ultima_det > POST_SEG or ahora - s.frames[0][0] > MAX_SEG:
                del self.sesiones[camara]
                self.cola.put(s)

    def cerrar_camara(self, camara):
        """La cámara se desconectó: se guarda lo que había grabado."""
        with self.lock:
            s = self.sesiones.pop(camara, None)
            self.buffers.pop(camara, None)
            self.seguidos.pop(camara, None)
            if s is not None:
                self.cola.put(s)

    def cerrar_todo(self, esperar=10.0):
        with self.lock:
            for s in self.sesiones.values():
                self.cola.put(s)
            self.sesiones.clear()
            self.buffers.clear()
            self.seguidos.clear()
        fin = time.time() + esperar
        while self.cola.unfinished_tasks and time.time() < fin:
            time.sleep(0.1)

    # ---------------------------------------------------------------- Escritura en disco
    def _trabajo(self):
        while True:
            s = self.cola.get()
            try:
                self._escribir(s)
                self._limpiar()
            except Exception:
                traceback.print_exc()
            finally:
                self.cola.task_done()

    def _escribir(self, s):
        frames = s.frames
        if len(frames) < 3:
            return
        dur = frames[-1][0] - frames[0][0]
        fps = min(30.0, max(2.0, len(frames) / dur)) if dur > 0 else 10.0
        primero = cv2.imdecode(np.frombuffer(frames[0][1], np.uint8), cv2.IMREAD_COLOR)
        if primero is None:
            return
        alto, ancho = primero.shape[:2]
        inicio = frames[0][0]
        base = f"{_limpio(s.camara)}_{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(inicio))}"
        n = 2
        while any(os.path.exists(os.path.join(self.carpeta, base + e)) for e in (".json", ".mp4", ".avi")):
            base = f"{base.rsplit('-', 1)[0] if base.endswith(f'-{n - 1}') else base}-{n}"
            n += 1
        escritor = None
        for codec, ext in (("mp4v", ".mp4"), ("MJPG", ".avi")):
            ruta = os.path.join(self.carpeta, base + ext)
            escritor = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*codec), fps, (ancho, alto))
            if escritor.isOpened():
                break
            escritor.release()
            escritor = None
        if escritor is None:
            print("[!] No se pudo crear el archivo de video de la grabación")
            return
        for _, jpg in frames:
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            if img.shape[:2] != (alto, ancho):
                img = cv2.resize(img, (ancho, alto))
            escritor.write(img)
        escritor.release()
        i = min(max(0, s.i_miniatura), len(frames) - 1)
        with open(os.path.join(self.carpeta, base + ".jpg"), "wb") as f:
            f.write(frames[i][1])
        with open(os.path.join(self.carpeta, base + ".json"), "w", encoding="utf-8") as f:
            json.dump({"camara": s.camara, "inicio": inicio, "duracion": round(dur, 1),
                       "fps": round(fps, 1), "video": base + ext}, f, ensure_ascii=False)
        if self.al_guardar:
            self.al_guardar(f"{s.camara}: clip guardado ({int(round(dur))} s)")

    # ---------------------------------------------------------------- Consulta y limpieza
    def _metas(self):
        metas = []
        try:
            nombres = os.listdir(self.carpeta)
        except OSError:
            return metas
        for n in nombres:
            if not n.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.carpeta, n), encoding="utf-8") as f:
                    m = json.load(f)
                id_ = n[:-5]
                ruta = os.path.join(self.carpeta, m["video"])
                if not os.path.exists(ruta):
                    continue
                m["id"] = id_
                m["tam"] = os.path.getsize(ruta)
                metas.append(m)
            except Exception:
                continue
        metas.sort(key=lambda m: m["inicio"], reverse=True)
        return metas

    def listar(self, limite=300):
        return [{"id": m["id"], "camara": m["camara"], "inicio": m["inicio"], "duracion": m["duracion"],
                 "tam": m["tam"]} for m in self._metas()[:limite]]

    def resumen(self):
        metas = self._metas()
        return {"activo": self.activo, "carpeta": self.carpeta, "usado": sum(m["tam"] for m in metas),
                "limite": int(LIMITE_GB * 1e9), "dias": DIAS_MAX}

    def _valido(self, id_):
        return bool(re.fullmatch(r"[\w\- ]+", id_ or ""))

    def ruta_video(self, id_):
        if not self._valido(id_):
            return None
        try:
            with open(os.path.join(self.carpeta, id_ + ".json"), encoding="utf-8") as f:
                ruta = os.path.join(self.carpeta, json.load(f)["video"])
            return ruta if os.path.exists(ruta) else None
        except Exception:
            return None

    def ruta_miniatura(self, id_):
        if not self._valido(id_):
            return None
        ruta = os.path.join(self.carpeta, id_ + ".jpg")
        return ruta if os.path.exists(ruta) else None

    def borrar(self, id_):
        if not self._valido(id_):
            return False
        hecho = False
        for ext in (".json", ".jpg", ".mp4", ".avi"):
            try:
                os.remove(os.path.join(self.carpeta, id_ + ext))
                hecho = True
            except OSError:
                pass
        return hecho

    def _limpiar(self):
        metas = self._metas()
        limite = time.time() - DIAS_MAX * 86400
        for m in list(metas):
            if m["inicio"] < limite:
                self.borrar(m["id"])
                metas.remove(m)
        total = sum(m["tam"] for m in metas)
        for m in reversed(metas):       # del más viejo al más nuevo
            if total <= LIMITE_GB * 1e9:
                break
            self.borrar(m["id"])
            total -= m["tam"]


PAGINA = r"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a0e13">
<title>MeCam · Grabaciones</title>
<style>
:root{--bg:#0a0e13;--panel:#111823;--panel2:#182231;--borde:#22314a;--texto:#e8eef6;--suave:#8fa3bb;--acento:#4f8cff;--rojo:#ef4444}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--texto);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
header{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;padding:14px 18px;border-bottom:1px solid var(--borde);
  background:linear-gradient(180deg,#0f1622,#0a0e13);position:sticky;top:0;z-index:5}
h1{font-size:18px;margin:0}
h1 small{color:var(--suave);font-weight:400;font-size:13px;margin-left:8px}
.espacio{flex:1}
a.boton,button,select{font:inherit;font-size:14px;color:var(--texto);background:var(--panel2);border:1px solid var(--borde);
  border-radius:10px;padding:8px 12px;cursor:pointer;text-decoration:none;display:inline-block}
a.boton:hover,button:hover,select:hover{border-color:var(--acento)}
button.peligro:hover{border-color:var(--rojo);color:#ffb4b4}
main{padding:16px}
#aviso{display:none;margin:0 0 14px;padding:10px 14px;border-radius:10px;background:#3a2a0b;border:1px solid #6b4a0f;color:#ffd58a;font-size:14px}
#resumen{color:var(--suave);font-size:13px;margin:0 0 14px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.clip{background:var(--panel);border:1px solid var(--borde);border-radius:14px;overflow:hidden;cursor:pointer}
.clip:hover{border-color:var(--acento)}
.mini{aspect-ratio:16/9;background:#000;position:relative}
.mini img{width:100%;height:100%;object-fit:cover;display:block}
.dur{position:absolute;right:8px;bottom:8px;background:rgba(0,0,0,.72);padding:2px 7px;border-radius:6px;font-size:12px}
.info{padding:10px 12px}.info b{display:block;font-size:14px}.info span{color:var(--suave);font-size:12px}
#vacio{display:none;text-align:center;color:var(--suave);padding:70px 20px;line-height:1.6}
#vacio h2{color:var(--texto);margin:0 0 6px;font-size:20px}
#modal{position:fixed;inset:0;background:rgba(3,5,8,.96);display:none;flex-direction:column;z-index:20}
#modal.abierto{display:flex}
.cab{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:12px 16px;padding-top:calc(12px + env(safe-area-inset-top))}
.cab b{font-size:16px}.cab span{color:var(--suave);font-size:13px}
.video{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;padding:0 12px 14px}
.video img{max-width:100%;max-height:100%;border-radius:12px;background:#000}
</style></head><body>
<header>
  <h1>MeCam<small>Grabaciones</small></h1>
  <span class="espacio"></span>
  <select id="filtro" title="Filtrar por cámara"><option value="">Todas las cámaras</option></select>
  <a class="boton" href="/ver">← Centro de control</a>
</header>
<main>
  <p id="aviso"></p>
  <p id="resumen"></p>
  <div class="grid" id="grid"></div>
  <div id="vacio"><h2>Todavía no hay grabaciones</h2>MeCam guarda un clip corto cada vez que detecta una persona.</div>
</main>
<div id="modal">
  <div class="cab">
    <b id="mTit"></b><span id="mSub"></span><span class="espacio"></span>
    <button id="mPrev" title="Anterior">◀</button><button id="mNext" title="Siguiente">▶</button>
    <button id="mRep">↻ Repetir</button><a class="boton" id="mDesc" href="#" download>⬇ Descargar</a>
    <button class="peligro" id="mBor">🗑 Borrar</button><button id="mCer">✕ Cerrar</button>
  </div>
  <div class="video"><img id="mImg" alt="grabación"></div>
</div>
<script>
(function () {
'use strict';
var $ = function (s) { return document.querySelector(s); };
var clips = [], resumen = {}, actual = null;

function dos(n) { return (n < 10 ? '0' : '') + n; }
function fmtFecha(t) {
  var d = new Date(t * 1000), hoy = new Date(), ayer = new Date(Date.now() - 86400000);
  var hora = dos(d.getHours()) + ':' + dos(d.getMinutes());
  if (d.toDateString() === hoy.toDateString()) return 'hoy ' + hora;
  if (d.toDateString() === ayer.toDateString()) return 'ayer ' + hora;
  return dos(d.getDate()) + '/' + dos(d.getMonth() + 1) + ' ' + hora;
}
function fmtDur(s) { s = Math.round(s); return Math.floor(s / 60) + ':' + dos(s % 60); }
function fmtTam(b) { return b > 1e9 ? (b / 1e9).toFixed(1) + ' GB' : (b / 1e6).toFixed(1) + ' MB'; }
function el(tag, clase, texto) { var e = document.createElement(tag); if (clase) e.className = clase; if (texto !== undefined) e.textContent = texto; return e; }
function url(base, id) { return base + encodeURIComponent(id); }

function visibles() { var f = $('#filtro').value; return clips.filter(function (c) { return !f || c.camara === f; }); }

function pintar() {
  var grid = $('#grid'), lista = visibles();
  grid.textContent = '';
  lista.forEach(function (c) {
    var caja = el('div', 'clip');
    var mini = el('div', 'mini'), img = el('img'); img.loading = 'lazy'; img.alt = ''; img.src = url('/miniatura/', c.id);
    mini.appendChild(img); mini.appendChild(el('span', 'dur', fmtDur(c.duracion)));
    var info = el('div', 'info'); info.appendChild(el('b', '', c.camara));
    info.appendChild(el('span', '', fmtFecha(c.inicio) + ' · ' + fmtTam(c.tam)));
    caja.appendChild(mini); caja.appendChild(info);
    caja.addEventListener('click', function () { abrir(c.id); });
    grid.appendChild(caja);
  });
  $('#vacio').style.display = lista.length ? 'none' : 'block';
  var av = $('#aviso');
  if (resumen.activo === false) { av.style.display = 'block'; av.textContent = 'La grabación está desactivada. Actívala en la ventana de MeCam (casilla «Grabar un clip…»).'; }
  else av.style.display = 'none';
  $('#resumen').textContent = lista.length + (lista.length === 1 ? ' clip' : ' clips') + ' · ' + fmtTam(resumen.usado || 0) +
    ' usados de ' + fmtTam(resumen.limite || 0) + ' · se borran solos los de más de ' + (resumen.dias || 30) + ' días';
}

function cargar() {
  return fetch('/api/grabaciones', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) {
    clips = d.clips || []; resumen = d;
    var sel = $('#filtro'), previo = sel.value, nombres = [];
    clips.forEach(function (c) { if (nombres.indexOf(c.camara) < 0) nombres.push(c.camara); });
    nombres.sort();
    sel.textContent = '';
    var todas = el('option', '', 'Todas las cámaras'); todas.value = ''; sel.appendChild(todas);
    nombres.forEach(function (n) { var o = el('option', '', n); o.value = n; sel.appendChild(o); });
    sel.value = nombres.indexOf(previo) >= 0 ? previo : '';
    pintar();
    if (actual && !clips.some(function (c) { return c.id === actual; })) cerrar();
  }).catch(function () {});
}

function abrir(id) {
  var c = clips.filter(function (x) { return x.id === id; })[0]; if (!c) return;
  actual = id;
  $('#mTit').textContent = c.camara; $('#mSub').textContent = fmtFecha(c.inicio) + ' · ' + fmtDur(c.duracion);
  $('#mDesc').href = url('/archivo/', id);
  $('#mImg').src = url('/clip/', id) + '?t=' + Date.now();
  $('#modal').classList.add('abierto');
}
function cerrar() { actual = null; $('#mImg').removeAttribute('src'); $('#modal').classList.remove('abierto'); }
function mover(d) {
  var l = visibles(); if (!l.length) return;
  var i = l.map(function (c) { return c.id; }).indexOf(actual);
  abrir(l[(i + d + l.length) % l.length].id);
}
function borrar() {
  if (!actual || !confirm('¿Borrar esta grabación? No se puede deshacer.')) return;
  var id = actual;
  fetch(url('/api/grabaciones/', id), { method: 'DELETE' }).then(function () { cerrar(); return cargar(); });
}

$('#filtro').addEventListener('change', pintar);
$('#mCer').addEventListener('click', cerrar);
$('#mPrev').addEventListener('click', function () { mover(-1); });
$('#mNext').addEventListener('click', function () { mover(1); });
$('#mRep').addEventListener('click', function () { if (actual) $('#mImg').src = url('/clip/', actual) + '?t=' + Date.now(); });
$('#mBor').addEventListener('click', borrar);
$('#modal').addEventListener('click', function (e) { if (e.target === $('#modal') || e.target.className === 'video') cerrar(); });
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') cerrar();
  else if (actual && e.key === 'ArrowLeft') mover(-1);
  else if (actual && e.key === 'ArrowRight') mover(1);
});
cargar(); setInterval(cargar, 5000);
})();
</script></body></html>
"""
