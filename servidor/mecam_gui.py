"""MeCam - ventana de control del servidor (boton verde "Iniciar servidor" y vinculacion por QR)."""
import ctypes
import os
import queue
import sys
import threading
import time
import traceback
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
except Exception:  # tkinter no instalado
    tk = None

COLA_LOG = queue.Queue()
ARCHIVO_LOG = os.path.join(BASE, "mecam.log")
PUERTO = 8443
FONDO, PANEL, PANEL2, TEXTO, SUAVE = "#0b0f14", "#141c28", "#1c2738", "#e8eef6", "#8fa3bb"
VERDE, VERDE_OSC = "#16a34a", "#15803d"
ROJO, ROJO_OSC = "#dc2626", "#b91c1c"
AZUL, AZUL_OSC = "#2563eb", "#1d4ed8"
AMBAR, GRIS = "#f59e0b", "#4b5563"


class Escritor:
    """Reemplaza stdout/stderr (con pythonw no existen) y manda todo a la ventana y a mecam.log."""
    encoding = "utf-8"
    errors = "replace"

    def __init__(self):
        try:
            self.f = open(ARCHIVO_LOG, "w", encoding="utf-8", errors="replace")
        except Exception:
            self.f = None

    def write(self, texto):
        if not texto:
            return 0
        if self.f:
            try:
                self.f.write(texto)
                self.f.flush()
            except Exception:
                pass
        COLA_LOG.put(texto)
        return len(texto)

    def flush(self):
        pass

    def isatty(self):
        return False


def boton(padre, texto, comando, **extra):
    opciones = dict(bg=PANEL2, fg=TEXTO, activebackground=GRIS, activeforeground=TEXTO,
                    relief="flat", cursor="hand2", padx=12, pady=5, font=("Segoe UI", 10))
    opciones.update(extra)
    return tk.Button(padre, text=texto, command=comando, **opciones)


class App:
    def __init__(self, root):
        self.root = root
        self.mod = None
        self.servidor = None
        self.estado = "detenido"      # detenido | cargando | activo | deteniendo
        self.ultimo_error = None
        self.eventos = queue.Queue()
        self.ids_lista = []           # id de cada fila de la lista de dispositivos
        self._filas = None
        # ventana del QR
        self.qr_win = None
        self.qr_token = None
        self.qr_nuevo_en = 0.0        # cuándo mostrar un QR nuevo tras vincular un dispositivo

        root.title("MeCam")
        root.geometry("620x820")
        root.minsize(540, 720)
        root.configure(bg=FONDO)
        root.protocol("WM_DELETE_WINDOW", self.cerrar)

        tk.Label(root, text="MeCam", font=("Segoe UI", 28, "bold"), fg=TEXTO, bg=FONDO).pack(pady=(16, 0))
        tk.Label(root, text="Cámaras de seguridad con celulares viejos",
                 font=("Segoe UI", 11), fg=SUAVE, bg=FONDO).pack()

        self.boton = tk.Button(
            root, text="▶  Iniciar servidor", command=self.alternar,
            font=("Segoe UI", 17, "bold"), bg=VERDE, fg="white",
            activebackground=VERDE_OSC, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", pady=14)
        self.boton.pack(fill="x", padx=40, pady=(18, 8))

        self.lbl_estado = tk.Label(root, text="● Detenido", font=("Segoe UI", 11, "bold"), fg=SUAVE,
                                   bg=FONDO, wraplength=520, justify="center")
        self.lbl_estado.pack()

        # Panel (solo visible con el servidor en marcha)
        self.contenedor = tk.Frame(root, bg=FONDO)
        self.contenedor.pack(fill="x", padx=40, pady=(10, 0))
        self.panel = tk.Frame(self.contenedor, bg=PANEL)
        self.var_ip = tk.StringVar()
        self.var_sin_vincular = tk.StringVar()

        tk.Button(self.panel, text="＋  Vincular dispositivo", command=self.abrir_qr,
                  font=("Segoe UI", 13, "bold"), bg=AZUL, fg="white", activebackground=AZUL_OSC,
                  activeforeground="white", relief="flat", bd=0, cursor="hand2", pady=10
                  ).pack(fill="x", padx=14, pady=(14, 10))

        tk.Label(self.panel, text="Dispositivos vinculados", font=("Segoe UI", 10), fg=SUAVE, bg=PANEL,
                 anchor="w").pack(fill="x", padx=14)
        fila = tk.Frame(self.panel, bg=PANEL)
        fila.pack(fill="x", padx=14, pady=(2, 0))
        self.lista = tk.Listbox(fila, height=5, bg=PANEL2, fg=TEXTO, selectbackground=AZUL,
                                selectforeground="white", relief="flat", highlightthickness=0,
                                font=("Segoe UI", 11), activestyle="none", exportselection=False)
        self.lista.pack(side="left", fill="x", expand=True)
        col = tk.Frame(fila, bg=PANEL)
        col.pack(side="left", padx=(8, 0), fill="y")
        boton(col, "Renombrar", self.renombrar, pady=3).pack(fill="x")
        boton(col, "Desvincular", self.desvincular, pady=3).pack(fill="x", pady=(6, 0))

        tk.Label(self.panel, textvariable=self.var_sin_vincular, font=("Segoe UI", 9), fg=AMBAR, bg=PANEL,
                 anchor="w", justify="left", wraplength=500).pack(fill="x", padx=14, pady=(6, 0))

        pie = tk.Frame(self.panel, bg=PANEL)
        pie.pack(fill="x", padx=14, pady=(10, 14))
        boton(pie, "Abrir centro de control", self.abrir_visor).pack(side="left")
        tk.Label(pie, textvariable=self.var_ip, font=("Segoe UI", 9), fg=SUAVE, bg=PANEL).pack(side="right")

        self.var_abrir = tk.BooleanVar(value=True)
        tk.Checkbutton(root, text="Abrir el centro de control al iniciar", variable=self.var_abrir,
                       bg=FONDO, fg=TEXTO, selectcolor=PANEL, activebackground=FONDO,
                       activeforeground=TEXTO, font=("Segoe UI", 10)).pack(pady=(12, 0))
        boton(root, "Abrir puertos del firewall (una sola vez)", self.abrir_firewall, bg=PANEL,
              pady=6).pack(pady=(8, 0))

        tk.Label(root, text="Detalles", font=("Segoe UI", 9), fg=SUAVE, bg=FONDO,
                 anchor="w").pack(fill="x", padx=40, pady=(14, 2))
        zona = tk.Frame(root, bg=FONDO)
        zona.pack(fill="both", expand=True, padx=40, pady=(0, 18))
        barra = tk.Scrollbar(zona)
        barra.pack(side="right", fill="y")
        self.log = tk.Text(zona, height=6, bg="#070a0e", fg=SUAVE, font=("Consolas", 9), relief="flat",
                           wrap="word", state="disabled", yscrollcommand=barra.set)
        self.log.pack(side="left", fill="both", expand=True)
        barra.config(command=self.log.yview)

        self.root.after(250, self.bucle)

    # ------------------------------------------------------------ Servidor
    @property
    def registro(self):
        return self.mod.registro

    def alternar(self):
        if self.estado == "detenido":
            self.iniciar()
        elif self.estado == "activo":
            self.detener()

    def iniciar(self):
        self.estado = "cargando"
        self.boton.config(text="Iniciando…", state="disabled", bg=GRIS)
        self.lbl_estado.config(text="● Cargando (la primera vez puede tardar unos minutos)…", fg=AMBAR)
        threading.Thread(target=self._arrancar, daemon=True).start()

    def _arrancar(self):
        ok = False
        self.ultimo_error = None
        try:
            import servidor
            self.mod = servidor
            self.servidor = servidor.Servidor()
            ok = self.servidor.iniciar()
            if not ok:
                self.ultimo_error = self.servidor.error
        except Exception as e:
            traceback.print_exc()
            self.ultimo_error = e
        self.eventos.put(("listo", ok))

    def _listo(self, ok):
        if ok:
            self.estado = "activo"
            self.var_ip.set(f"IP de esta computadora: {self.servidor.ip}")
            self.boton.config(text="■  Detener servidor", state="normal", bg=ROJO, activebackground=ROJO_OSC)
            self.panel.pack(fill="x")
            if self.var_abrir.get():
                self.abrir_visor()
            return
        self.estado = "detenido"
        self.boton.config(text="▶  Iniciar servidor", state="normal", bg=VERDE, activebackground=VERDE_OSC)
        self.lbl_estado.config(text="● Detenido", fg=SUAVE)
        err = self.ultimo_error
        if isinstance(err, OSError) and (getattr(err, "winerror", None) == 10048 or err.errno in (98, 10048)):
            msg = ("Los puertos 8443 y 8080 ya están en uso.\n\n¿Hay otro MeCam abierto, o la ventana negra "
                   "de antes? Ciérralo e inténtalo de nuevo.")
        elif isinstance(err, ImportError):
            msg = (f"Falta instalar algo: {err}\n\nBorra el archivo «.instalado-v2» de la carpeta y abre "
                   "«Iniciar MeCam.bat» de nuevo: instala lo necesario en el primer arranque.")
        elif err is not None:
            msg = (f"No se pudo iniciar el servidor:\n\n{err}\n\nSi es la primera vez, revisa tu conexión a "
                   "internet (se descarga el modelo de detección).")
        else:
            msg = "No se pudo iniciar el servidor. Mira el recuadro «Detalles» de abajo."
        messagebox.showerror("MeCam", msg)

    def detener(self):
        self.cerrar_qr()
        self.estado = "deteniendo"
        self.boton.config(text="Deteniendo…", state="disabled", bg=GRIS)
        threading.Thread(target=self._parar, daemon=True).start()

    def _parar(self):
        try:
            self.servidor.detener()
        except Exception:
            traceback.print_exc()
        self.eventos.put(("detenido", None))

    def _detenido(self):
        self.estado = "detenido"
        self.panel.pack_forget()
        self.boton.config(text="▶  Iniciar servidor", state="normal", bg=VERDE, activebackground=VERDE_OSC)
        self.lbl_estado.config(text="● Detenido", fg=SUAVE)

    def abrir_visor(self):
        webbrowser.open(f"https://localhost:{PUERTO}/ver")

    def abrir_firewall(self):
        """Pide permiso de administrador (Windows lo pregunta) y abre los dos puertos de MeCam."""
        comando = (
            '/c netsh advfirewall firewall delete rule name="MeCam" >nul 2>&1 & '
            'netsh advfirewall firewall delete rule name="MeCam8080" >nul 2>&1 & '
            'netsh advfirewall firewall add rule name="MeCam" dir=in action=allow protocol=TCP localport=8443 & '
            'netsh advfirewall firewall add rule name="MeCam8080" dir=in action=allow protocol=TCP localport=8080 & '
            "echo. & echo Listo. Puedes cerrar esta ventana. & pause"
        )
        try:
            r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", comando, None, 1)
            if r <= 32:
                messagebox.showwarning("MeCam", "No se pudo pedir el permiso de administrador.")
        except Exception:
            messagebox.showwarning("MeCam", "Esta función solo está disponible en Windows.")

    def cerrar(self):
        try:
            self.root.destroy()
        finally:
            os._exit(0)

    # ------------------------------------------------------------ Dispositivos vinculados
    def _seleccionado(self):
        sel = self.lista.curselection()
        if not sel or sel[0] >= len(self.ids_lista):
            messagebox.showinfo("MeCam", "Primero elige un dispositivo de la lista.")
            return None
        return self.ids_lista[sel[0]]

    def renombrar(self):
        disp_id = self._seleccionado()
        if disp_id is None:
            return
        actual = next((d["nombre"] for d in self.registro.lista() if d["id"] == disp_id), "")
        nuevo = simpledialog.askstring("Renombrar", "Nuevo nombre:", initialvalue=actual, parent=self.root)
        if nuevo and not self.registro.renombrar(disp_id, nuevo):
            messagebox.showwarning("MeCam", "Ese nombre no sirve: está vacío o ya lo usa otro dispositivo.")

    def desvincular(self):
        disp_id = self._seleccionado()
        if disp_id is None:
            return
        nombre = next((d["nombre"] for d in self.registro.lista() if d["id"] == disp_id), "")
        if messagebox.askyesno("Desvincular", f"¿Desvincular «{nombre}»?\n\nDejará de poder conectarse."):
            self.servidor.desvincular(disp_id)

    def _refrescar_lista(self):
        en_linea = set()
        try:
            en_linea = {c.id for c in list(self.mod.camaras.values())}
        except RuntimeError:
            pass
        filas = []
        for d in self.registro.lista():
            punto = "●" if d["id"] in en_linea else "○"
            tipo = "cámara" if d["tipo"] == "camara" else "visor"
            modelo = f"  ·  {d['modelo']}" if d.get("modelo") and d["tipo"] == "camara" else ""
            filas.append((d["id"], f"{punto}  {d['nombre']}  ·  {tipo}{modelo}"))
        if filas != self._filas:
            elegido = self.ids_lista[self.lista.curselection()[0]] if self.lista.curselection() else None
            self._filas = filas
            self.ids_lista = [f[0] for f in filas]
            self.lista.delete(0, "end")
            for _, texto in filas:
                self.lista.insert("end", texto)
            if elegido in self.ids_lista:
                self.lista.selection_set(self.ids_lista.index(elegido))
        # cámaras conectadas que todavía no están vinculadas
        vinculadas = {d["id"] for d in self.registro.lista()}
        libres = sorted(c.nombre for c in list(self.mod.camaras.values()) if c.id not in vinculadas)
        self.var_sin_vincular.set(
            ("Sin vincular: " + ", ".join(libres) + ". Usa «Vincular dispositivo» para protegerlas.") if libres else "")

    def _refrescar_estado(self):
        if self.registro.proteccion:
            self.lbl_estado.config(text="● En marcha  ·  Protegido: solo entran dispositivos vinculados",
                                   fg="#22c55e")
        else:
            self.lbl_estado.config(
                text="● En marcha  ·  Abierto: cualquiera en tu red puede conectarse. "
                     "Vincula un dispositivo para protegerlo.", fg=AMBAR)

    # ------------------------------------------------------------ QR
    def abrir_qr(self):
        if self.qr_win is not None:
            self.qr_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("Vincular dispositivo")
        win.configure(bg=FONDO)
        win.resizable(False, False)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self.cerrar_qr)
        self.qr_win = win
        tk.Label(win, text="Vincular dispositivo", font=("Segoe UI", 18, "bold"), fg=TEXTO, bg=FONDO).pack(pady=(16, 4))
        tk.Label(win, text="Escanea este QR:", font=("Segoe UI", 11), fg=SUAVE, bg=FONDO).pack()
        self.qr_canvas = tk.Canvas(win, width=300, height=300, bg="white", highlightthickness=0)
        self.qr_canvas.pack(pady=12)
        self.qr_info = tk.Label(win, text="", font=("Segoe UI", 10), fg=SUAVE, bg=FONDO)
        self.qr_info.pack()
        self.qr_msg = tk.Label(win, text="", font=("Segoe UI", 12, "bold"), fg="#22c55e", bg=FONDO,
                               wraplength=380)
        self.qr_msg.pack(pady=(4, 0))
        tk.Label(win, justify="left", wraplength=380, font=("Segoe UI", 10), fg=TEXTO, bg=FONDO, text=(
            "•  Para una CÁMARA: abre la app MeCam en el celular y toca «Escanear QR para vincular».\n\n"
            "•  Para VER las cámaras: escanéalo con la cámara normal del celular (o del otro aparato) y "
            "abre el enlace.\n\n"
            "Cada QR sirve una sola vez y vence en unos minutos. Al usarlo, aparece uno nuevo para el "
            "siguiente dispositivo.")).pack(padx=30, pady=(14, 0))
        boton(win, "Cerrar", self.cerrar_qr).pack(pady=14)
        self._nuevo_qr()

    def _nuevo_qr(self):
        if self.qr_win is None:
            return
        if self.qr_token:
            self.registro.anular_token(self.qr_token)
        self.qr_token, url = self.servidor.nuevo_qr()
        self.qr_nuevo_en = 0.0
        self._dibujar_qr(url)

    def _dibujar_qr(self, url):
        try:
            import qrcode
        except ImportError:
            self.cerrar_qr()
            messagebox.showerror("MeCam", "Falta instalar el componente del QR.\n\nCierra MeCam, borra el archivo "
                                 "«.instalado-v2» de la carpeta (si existe) y abre «Iniciar MeCam.bat» de nuevo.")
            return
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        m = qr.get_matrix()
        celda = max(1, 300 // len(m))
        tam = celda * len(m)
        c = self.qr_canvas
        c.delete("all")
        c.config(width=tam, height=tam)
        for y, fila in enumerate(m):
            for x, oscuro in enumerate(fila):
                if oscuro:
                    c.create_rectangle(x * celda, y * celda, (x + 1) * celda, (y + 1) * celda,
                                       fill="black", width=0)

    def cerrar_qr(self):
        if self.qr_token and self.mod is not None:
            self.registro.anular_token(self.qr_token)
        self.qr_token = None
        if self.qr_win is not None:
            self.qr_win.destroy()
        self.qr_win = None

    def _tick_qr(self):
        if self.qr_win is None or not self.qr_token:
            return
        est = self.registro.estado_token(self.qr_token)
        if est == "vigente":
            s = self.registro.segundos_restantes(self.qr_token)
            self.qr_info.config(text=f"Vence en {s // 60}:{s % 60:02d}")
        elif est == "usado":
            if not self.qr_nuevo_en:
                ultimo = max(self.registro.lista(), key=lambda d: d["creado"], default=None)
                self.qr_msg.config(text=f"✓ Vinculado: {ultimo['nombre']}" if ultimo else "✓ Vinculado")
                self.qr_nuevo_en = time.time() + 2.5
            elif time.time() >= self.qr_nuevo_en:
                self.qr_msg.config(text="")
                self._nuevo_qr()
        else:   # vencido
            self._nuevo_qr()

    # ------------------------------------------------------------ Actualización periódica
    def bucle(self):
        try:
            texto = ""
            while True:
                try:
                    texto += COLA_LOG.get_nowait()
                except queue.Empty:
                    break
            if texto:
                self.log.config(state="normal")
                self.log.insert("end", texto.replace("\r", ""))
                if int(self.log.index("end-1c").split(".")[0]) > 500:
                    self.log.delete("1.0", "150.0")
                self.log.see("end")
                self.log.config(state="disabled")
            while True:
                try:
                    ev, dato = self.eventos.get_nowait()
                except queue.Empty:
                    break
                if ev == "listo":
                    self._listo(dato)
                elif ev == "detenido":
                    self._detenido()
            if self.estado == "activo" and self.mod is not None:
                self._refrescar_lista()
                self._refrescar_estado()
                self._tick_qr()
        except Exception:
            traceback.print_exc()
        finally:
            self.root.after(250, self.bucle)


def main():
    sys.stdout = sys.stderr = Escritor()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)   # ventana nítida en pantallas de alta resolución
    except Exception:
        pass
    if tk is None:
        with open(os.path.join(BASE, "mecam_error.log"), "w", encoding="utf-8") as f:
            f.write("Este Python no incluye tkinter (necesario para la ventana).\n"
                    "Reinstala Python desde python.org y deja marcada la opcion tcl/tk.\n")
        try:
            ctypes.windll.user32.MessageBoxW(0, "Este Python no incluye tkinter. Reinstala Python desde "
                                                "python.org.", "MeCam", 0x10)
        except Exception:
            pass
        return
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:
        error = traceback.format_exc()
        with open(os.path.join(BASE, "mecam_error.log"), "w", encoding="utf-8") as f:
            f.write(error)
        try:
            messagebox.showerror("MeCam", "La ventana no pudo abrirse. Detalles en mecam_error.log")
        except Exception:
            pass


if __name__ == "__main__":
    main()
