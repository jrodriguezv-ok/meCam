"""
MeCam - vinculación de dispositivos por QR.

- Cada QR lleva un código de UN SOLO USO que vence a los pocos minutos.
- Al canjearlo, el dispositivo recibe su propia credencial permanente
  (el servidor solo guarda una huella de ella, nunca la credencial).
- El certificado HTTPS se crea una sola vez y su huella viaja dentro del QR:
  las cámaras se conectan cifradas y solo con esta computadora.
"""
import base64
import datetime
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import subprocess
import threading
import time

MINUTOS_QR = 5
CONFIAR_LOCAL = True     # esta misma computadora no necesita vincularse
TS_ACTIVO = False        # True si Tailscale está instalado y conectado en esta computadora
_RED_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")


def carpeta_datos():
    """Carpeta donde se guardan los dispositivos y el certificado (sobrevive a las actualizaciones)."""
    ruta = os.environ.get("MECAM_DATOS")
    if not ruta:
        appdata = os.environ.get("APPDATA")
        ruta = os.path.join(appdata, "MeCam") if appdata else os.path.join(os.path.expanduser("~"), ".mecam")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def _huella_secreto(secreto):
    return hashlib.sha256(secreto.encode()).hexdigest()


class Registro:
    """Dispositivos vinculados y códigos QR pendientes."""

    def __init__(self, ruta=None):
        self.ruta = ruta or os.path.join(carpeta_datos(), "dispositivos.json")
        self.lock = threading.RLock()
        self.dispositivos = {}   # id -> datos
        self.pendientes = {}     # código -> cuándo vence
        self.usados = {}         # código -> cuándo se usó
        self._cargar()

    def _cargar(self):
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
            self.dispositivos = {d["id"]: d for d in datos.get("dispositivos", [])}
        except Exception:
            self.dispositivos = {}

    def _guardar(self):
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"dispositivos": list(self.dispositivos.values())}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.ruta)

    @property
    def proteccion(self):
        """Hay al menos un dispositivo vinculado: desde ese momento solo entran los vinculados."""
        with self.lock:
            return bool(self.dispositivos)

    # ---- códigos QR de un solo uso
    def nuevo_token(self, minutos=MINUTOS_QR):
        with self.lock:
            ahora = time.time()
            self.pendientes = {t: e for t, e in self.pendientes.items() if e > ahora}
            token = secrets.token_urlsafe(16)
            self.pendientes[token] = ahora + minutos * 60
            return token

    def estado_token(self, token):
        with self.lock:
            if token in self.usados:
                return "usado"
            exp = self.pendientes.get(token)
            if exp is None:
                return "desconocido"
            return "vigente" if exp > time.time() else "vencido"

    def anular_token(self, token):
        with self.lock:
            self.pendientes.pop(token, None)

    def segundos_restantes(self, token):
        with self.lock:
            return max(0, int(self.pendientes.get(token, 0) - time.time()))

    def canjear_token(self, token):
        """Usa el código. Devuelve True una sola vez; después ya no sirve."""
        with self.lock:
            exp = self.pendientes.pop(token, None)
            if exp is None or exp < time.time():
                return False
            self.usados[token] = time.time()
            return True

    # ---- dispositivos
    def vincular(self, tipo, modelo=""):
        """Registra un dispositivo nuevo. Devuelve (id, secreto, nombre)."""
        with self.lock:
            base = "Cámara" if tipo == "camara" else "Visor"
            usados = {d["nombre"] for d in self.dispositivos.values()}
            n = 1
            while f"{base} {n}" in usados:
                n += 1
            nombre = f"{base} {n}"
            disp_id = secrets.token_hex(8)
            secreto = secrets.token_urlsafe(24)
            self.dispositivos[disp_id] = {
                "id": disp_id, "tipo": tipo, "nombre": nombre, "modelo": modelo[:60],
                "hash": _huella_secreto(secreto), "creado": time.time(), "visto": 0,
            }
            self._guardar()
            return disp_id, secreto, nombre

    def revincular(self, disp_id, modelo=""):
        """Le da una credencial nueva a un dispositivo que ya existe (así un celular no se duplica)."""
        with self.lock:
            d = self.dispositivos.get(disp_id)
            if d is None:
                return None
            secreto = secrets.token_urlsafe(24)
            d["hash"] = _huella_secreto(secreto)
            if modelo:
                d["modelo"] = modelo[:60]
            self._guardar()
            return d["id"], secreto, d["nombre"]

    def verificar(self, credencial):
        """Comprueba 'id.secreto'. Devuelve los datos del dispositivo o None."""
        if not credencial or "." not in credencial:
            return None
        disp_id, secreto = credencial.split(".", 1)
        with self.lock:
            d = self.dispositivos.get(disp_id)
            if d is None or not hmac.compare_digest(_huella_secreto(secreto), d["hash"]):
                return None
            d["visto"] = time.time()
            return dict(d)

    def desvincular(self, disp_id):
        with self.lock:
            if self.dispositivos.pop(disp_id, None) is not None:
                self._guardar()
                return True
            return False

    def renombrar(self, disp_id, nombre):
        nombre = " ".join(nombre.split())[:32]
        with self.lock:
            d = self.dispositivos.get(disp_id)
            if d is None or not nombre:
                return False
            if any(o["nombre"] == nombre and o["id"] != disp_id for o in self.dispositivos.values()):
                return False
            d["nombre"] = nombre
            self._guardar()
            return True

    def lista(self):
        with self.lock:
            return sorted((dict(d) for d in self.dispositivos.values()), key=lambda d: (d["tipo"], d["nombre"]))


# ---------------------------------------------------------------- Certificado fijo
def asegurar_certificado(ip):
    """Devuelve (ruta_cert, ruta_clave, huella). Se crea una sola vez, para que los dispositivos vinculados lo reconozcan siempre."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    carpeta = carpeta_datos()
    ruta_cert = os.path.join(carpeta, "certificado.pem")
    ruta_clave = os.path.join(carpeta, "clave.pem")
    if not (os.path.exists(ruta_cert) and os.path.exists(ruta_clave)):
        clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MeCam")])
        ahora = datetime.datetime.now(datetime.timezone.utc)
        nombres = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
        try:
            if ip != "127.0.0.1":
                nombres.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            pass
        cert = (
            x509.CertificateBuilder()
            .subject_name(nombre)
            .issuer_name(nombre)
            .public_key(clave.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(ahora - datetime.timedelta(days=1))
            .not_valid_after(ahora + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(nombres), critical=False)
            .sign(clave, hashes.SHA256())
        )
        with open(ruta_cert, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(ruta_clave, "wb") as f:
            f.write(clave.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
    with open(ruta_cert, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    der = cert.public_bytes(serialization.Encoding.DER)
    huella = base64.urlsafe_b64encode(hashlib.sha256(der).digest()).rstrip(b"=").decode()
    return ruta_cert, ruta_clave, huella


# ---------------------------------------------------------------- Quién puede entrar sin vincularse
def refrescar_tailscale():
    """Detecta si esta computadora está conectada a Tailscale (para aceptar a tus dispositivos de esa red)."""
    global TS_ACTIVO
    activo = False
    for exe in ("tailscale", r"C:\Program Files\Tailscale\tailscale.exe"):
        try:
            r = subprocess.run(
                [exe, "ip", "-4"], capture_output=True, text=True, timeout=4,
                creationflags=0x08000000 if os.name == "nt" else 0,   # sin ventana negra
            )
            if r.returncode == 0 and r.stdout.strip():
                ip = ipaddress.ip_address(r.stdout.strip().splitlines()[0].strip())
                activo = ip in _RED_TAILSCALE
                break
        except Exception:
            continue
    TS_ACTIVO = activo
    return activo


def es_confiable(remoto):
    """Sin vincular se aceptan: esta misma computadora y, con Tailscale activo, los dispositivos de tu red Tailscale."""
    try:
        ip = ipaddress.ip_address(remoto or "")
    except ValueError:
        return False
    if ip.is_loopback:
        return CONFIAR_LOCAL
    return bool(TS_ACTIVO and ip.version == 4 and ip in _RED_TAILSCALE)


def credencial(request):
    """La credencial llega en la cabecera Authorization (app) o en la cookie 'mecam' (navegador)."""
    h = request.headers.get("Authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.cookies.get("mecam", "")
