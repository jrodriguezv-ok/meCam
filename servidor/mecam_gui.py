"""MeCam - ventana de control del servidor (boton verde "Iniciar servidor")."""
import ctypes
import os
import queue
import sys
import threading
import traceback
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

try:
    import tkinter as tk
    from tkinter import messagebox
except Exception:  # tkinter no instalado
    tk = None

COLA_LOG = queue.Queue()
ARCHIVO_LOG = os.path.join(BASE, "mecam.log")
PUERTO = 8443
FONDO, PANEL, PANEL2, TEXTO, SUAVE = "#0b0f14", "#141c28", "#1c2738", "#e8eef6", "#8fa3bb"
VERDE, VERDE_OSC = "#16a34a", "#15803d"
ROJO, ROJO_OSC = "#dc2626", "#b91c1c"
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


class App:
    def __init__(self, root):
        self.root = root
        self.mod = None
        self.servidor = None
        self.estado = "detenido"      # detenido | cargando | activo | deteniendo
        self.ultimo_error = None
        self.eventos = queue.Queue()

        root.title("MeCam")
        root.geometry("600x700")
        root.minsize(520, 620)
        root.configure(bg=FONDO)
        root.protocol("WM_DELETE_WINDOW", self.cerrar)

        tk.Label(root, text="MeCam", font=("Segoe UI", 28, "bold"), fg=TEXTO, bg=FONDO).pack(pady=(18, 0))
        tk.Label(root, text="Cámaras de seguridad con celulares viejos",
                 font=("Segoe UI", 11), fg=SUAVE, bg=FONDO).pack()

        self.boton = tk.Button(
            root, text="▶  Iniciar servidor", command=self.alternar,
            font=("Segoe UI", 17, "bold"), bg=VERDE, fg="white",
            activebackground=VERDE_OSC, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", pady=14)
        self.boton.pack(fill="x", padx=40, pady=(20, 8))

        self.lbl_estado = tk.Label(root, text="● Detenido", font=("Segoe UI", 11, "bold"), fg=SUAVE, bg=FONDO)
        self.lbl_estado.pack()

        # Panel con las direcciones (solo visible con el servidor en marcha)
        self.contenedor = tk.Frame(root, bg=FONDO)
        self.contenedor.pack(fill="x", padx=40, pady=(10, 0))
        self.panel = tk.Frame(self.contenedor, bg=PANEL)
        self.var_ip = tk.StringVar()
        self.var_url = tk.StringVar(value=f"https://localhost:{PUERTO}/ver")
        self.var_camaras = tk.StringVar(value="ninguna todavía")

        tk.Label(self.panel, text="En la app MeCam de cada celular escribe esta IP:",
                 font=("Segoe UI", 10), fg=SUAVE, bg=PANEL, anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        fila = tk.Frame(self.panel, bg=PANEL)
        fila.pack(fill="x", padx=14)
        tk.Entry(fila, textvariable=self.var_ip, state="readonly", readonlybackground=PANEL2, fg=TEXTO,
                 relief="flat", font=("Segoe UI", 15, "bold")).pack(side="left", fill="x", expand=True, ipady=6)
        self.btn_copiar = tk.Button(fila, text="Copiar", command=self.copiar_ip, bg=PANEL2, fg=TEXTO,
                                    activebackground=GRIS, activeforeground=TEXTO, relief="flat",
                                    cursor="hand2", padx=12)
        self.btn_copiar.pack(side="left", padx=(8, 0), fill="y")

        tk.Label(self.panel, text="Centro de control (para ver las cámaras):",
                 font=("Segoe UI", 10), fg=SUAVE, bg=PANEL, anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        fila2 = tk.Frame(self.panel, bg=PANEL)
        fila2.pack(fill="x", padx=14)
        tk.Entry(fila2, textvariable=self.var_url, state="readonly", readonlybackground=PANEL2, fg=TEXTO,
                 relief="flat", font=("Segoe UI", 11)).pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(fila2, text="Abrir visor", command=self.abrir_visor, bg=PANEL2, fg=TEXTO,
                  activebackground=GRIS, activeforeground=TEXTO, relief="flat", cursor="hand2",
                  padx=12).pack(side="left", padx=(8, 0), fill="y")

        tk.Label(self.panel, text="Cámaras conectadas:", font=("Segoe UI", 10), fg=SUAVE, bg=PANEL,
                 anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(self.panel, textvariable=self.var_camaras, font=("Segoe UI", 12, "bold"), fg=TEXTO,
                 bg=PANEL, anchor="w", justify="left", wraplength=480).pack(fill="x", padx=14, pady=(0, 12))

        self.var_abrir = tk.BooleanVar(value=True)
        tk.Checkbutton(root, text="Abrir el centro de control al iniciar", variable=self.var_abrir,
                       bg=FONDO, fg=TEXTO, selectcolor=PANEL, activebackground=FONDO,
                       activeforeground=TEXTO, font=("Segoe UI", 10)).pack(pady=(12, 0))
        tk.Button(root, text="Abrir puertos del firewall (una sola vez)", command=self.abrir_firewall,
                  bg=PANEL, fg=TEXTO, activebackground=GRIS, activeforeground=TEXTO, relief="flat",
                  cursor="hand2", padx=12, pady=6, font=("Segoe UI", 10)).pack(pady=(8, 0))

        tk.Label(root, text="Detalles", font=("Segoe UI", 9), fg=SUAVE, bg=FONDO,
                 anchor="w").pack(fill="x", padx=40, pady=(14, 2))
        zona = tk.Frame(root, bg=FONDO)
        zona.pack(fill="both", expand=True, padx=40, pady=(0, 18))
        barra = tk.Scrollbar(zona)
        barra.pack(side="right", fill="y")
        self.log = tk.Text(zona, height=8, bg="#070a0e", fg=SUAVE, font=("Consolas", 9), relief="flat",
                           wrap="word", state="disabled", yscrollcommand=barra.set)
        self.log.pack(side="left", fill="both", expand=True)
        barra.config(command=self.log.yview)

        self.root.after(250, self.bucle)

    # ------------------------------------------------------------ Acciones
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
            self.var_ip.set(self.servidor.ip)
            self.boton.config(text="■  Detener servidor", state="normal", bg=ROJO, activebackground=ROJO_OSC)
            self.lbl_estado.config(text="● En marcha", fg="#22c55e")
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
            msg = (f"Falta instalar algo: {err}\n\nCierra esta ventana y abre «Iniciar MeCam.bat» de nuevo: "
                   "instala lo necesario en el primer arranque.")
        elif err is not None:
            msg = (f"No se pudo iniciar el servidor:\n\n{err}\n\nSi es la primera vez, revisa tu conexión a "
                   "internet (se descarga el modelo de detección).")
        else:
            msg = "No se pudo iniciar el servidor. Mira el recuadro «Detalles» de abajo."
        messagebox.showerror("MeCam", msg)

    def detener(self):
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
        self.var_camaras.set("ninguna todavía")
        self.boton.config(text="▶  Iniciar servidor", state="normal", bg=VERDE, activebackground=VERDE_OSC)
        self.lbl_estado.config(text="● Detenido", fg=SUAVE)

    def copiar_ip(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.var_ip.get())
        self.root.update()
        self.btn_copiar.config(text="¡Copiado!")
        self.root.after(1500, lambda: self.btn_copiar.config(text="Copiar"))

    def abrir_visor(self):
        webbrowser.open(self.var_url.get())

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
                try:
                    nombres = sorted(self.mod.camaras.keys())
                except RuntimeError:
                    nombres = None
                if nombres is not None:
                    self.var_camaras.set(", ".join(nombres) if nombres else "ninguna todavía")
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
