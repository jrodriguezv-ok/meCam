package com.mecam.app

import android.Manifest
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

class MainActivity : ComponentActivity() {

    private companion object {
        val VERDE = 0xFF16A34A.toInt()
        val ROJO = 0xFFDC2626.toInt()
        val AMBAR = 0xFFF59E0B.toInt()
        val AZUL = 0xFF2563EB.toInt()
        val BLANCO = 0xFFFFFFFF.toInt()
    }

    private lateinit var campoIp: EditText
    private lateinit var campoNombre: EditText
    private lateinit var campoFps: EditText
    private lateinit var campoOrientacion: Spinner
    private lateinit var botonActualizar: Button
    private lateinit var botonOlvidar: Button
    private lateinit var botonPrincipal: Button
    private lateinit var tarjeta: TextView
    private lateinit var ajustes: LinearLayout
    private lateinit var estado: TextView
    private lateinit var textoEstado: TextView
    private lateinit var cartel: TextView
    private lateinit var luzRoja: View
    private lateinit var luzAmbar: View
    private lateinit var luzVerde: View

    private val manejador = Handler(Looper.getMainLooper())
    private var cartelNombre: String? = null      // nombre con el que se acaba de vincular (para el cartel verde)

    private val pedirPermisos = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        if (tieneCamara()) {
            iniciarServicio()
        } else {
            estado.text = "Falta el permiso de cámara. Toca «Encender cámara» y elige Permitir."
        }
    }

    private val escanear = registerForActivityResult(ScanContract()) { resultado ->
        val texto = resultado.contents
        if (texto != null) vincularConQr(texto)
    }

    private fun prefs(): SharedPreferences = getSharedPreferences("mecam", Context.MODE_PRIVATE)

    private fun tieneCamara() = ContextCompat.checkSelfPermission(
        this, Manifest.permission.CAMERA
    ) == PackageManager.PERMISSION_GRANTED

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun fondo(color: Int, radio: Int = 16) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = dp(radio).toFloat()
        setColor(color)
    }

    private fun nuevaLuz() = View(this).apply {
        layoutParams = LinearLayout.LayoutParams(dp(46), dp(46)).apply { setMargins(dp(9), 0, dp(9), 0) }
    }

    private fun pintarLuz(luz: View, color: Int, encendida: Boolean) {
        luz.background = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(if (encendida) color else ((color and 0x00FFFFFF) or 0x33000000))
            setStroke(dp(2), if (encendida) color else 0x33FFFFFF)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = prefs()
        val pad = dp(20)

        val raiz = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
        }
        val titulo = TextView(this).apply {
            text = "MeCam (versión ${Actualizador.versionInstalada(this@MainActivity)})"
            textSize = 28f
        }
        botonActualizar = Button(this).apply {
            visibility = View.GONE
            setOnClickListener { actualizar() }
        }
        cartel = TextView(this).apply {
            visibility = View.GONE
            textSize = 16f
            setTextColor(BLANCO)
            setPadding(dp(14), dp(12), dp(14), dp(12))
            background = fondo(VERDE, 12)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(0, dp(10), 0, dp(6)) }
        }
        tarjeta = TextView(this).apply {
            textSize = 16f
            setPadding(0, pad / 2, 0, pad / 2)
        }
        val botonQr = Button(this).apply {
            text = "Escanear QR para vincular"
            textSize = 16f
            isAllCaps = false
            setTextColor(BLANCO)
            background = fondo(AZUL, 14)
            setOnClickListener { lanzarEscaner() }
        }

        // Semáforo: rojo = detenida, amarillo = conectando o en pausa, verde = transmitiendo
        luzRoja = nuevaLuz()
        luzAmbar = nuevaLuz()
        luzVerde = nuevaLuz()
        val semaforo = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, dp(18), 0, dp(6))
            addView(luzRoja)
            addView(luzAmbar)
            addView(luzVerde)
        }
        textoEstado = TextView(this).apply {
            textSize = 18f
            gravity = Gravity.CENTER
            setPadding(0, dp(4), 0, dp(6))
        }
        botonPrincipal = Button(this).apply {
            textSize = 20f
            isAllCaps = false
            setTextColor(BLANCO)
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(68)
            ).apply { setMargins(0, dp(8), 0, dp(8)) }
            setOnClickListener {
                if (EstadoCamara.fase == Fase.DETENIDA) pedir() else detener()
            }
        }

        // Ajustes (escondidos para que la pantalla principal sea simple)
        campoFps = EditText(this).apply {
            hint = "Cuadros por segundo (1 a 25, ej: 10)"
            inputType = InputType.TYPE_CLASS_NUMBER
            setText(prefs.getInt("fps", 10).toString())
        }
        campoOrientacion = Spinner(this).apply {
            adapter = ArrayAdapter(
                this@MainActivity,
                android.R.layout.simple_spinner_dropdown_item,
                listOf(
                    "Orientación: automática",
                    "Orientación: vertical",
                    "Orientación: horizontal (girado a la izquierda)",
                    "Orientación: horizontal (girado a la derecha)"
                )
            )
            setSelection(prefs.getInt("orientacion", 0))
        }
        val botonBateria = Button(this).apply {
            text = "Ajustes de batería (para que no se cierre)"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
        }
        botonOlvidar = Button(this).apply {
            text = "Olvidar la computadora vinculada"
            setOnClickListener { olvidar() }
        }
        val etiquetaManual = TextView(this).apply {
            text = "Conexión manual (solo si no puedes usar el QR):"
            setPadding(0, pad / 2, 0, 0)
        }
        campoIp = EditText(this).apply {
            hint = "IP de la computadora (ej: 192.168.1.128)"
            setText(prefs.getString("ip", ""))
        }
        campoNombre = EditText(this).apply {
            hint = "Nombre de esta cámara (ej: celular1)"
            setText(prefs.getString("nombre", "celular1"))
        }
        ajustes = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }
        listOf(campoFps, campoOrientacion, botonBateria, botonOlvidar, etiquetaManual, campoIp, campoNombre)
            .forEach { ajustes.addView(it) }
        val botonAjustes = Button(this).apply {
            text = "Ajustes ▾"
            setOnClickListener {
                val abierto = ajustes.visibility == View.VISIBLE
                ajustes.visibility = if (abierto) View.GONE else View.VISIBLE
                text = if (abierto) "Ajustes ▾" else "Ajustes ▴"
            }
        }
        estado = TextView(this).apply {
            textSize = 16f
            setPadding(0, pad / 2, 0, 0)
        }

        listOf(
            titulo, botonActualizar, cartel, tarjeta, botonQr, semaforo, textoEstado, botonPrincipal,
            estado, botonAjustes, ajustes
        ).forEach { raiz.addView(it) }
        setContentView(ScrollView(this).apply { addView(raiz) })

        actualizarTarjeta()
        refrescarEstado()
        revisarActualizacion()

        // Si la cámara estaba encendida (por ejemplo antes de actualizar), se reanuda al abrir la app
        val hayConexion = Vinculo.vinculada(this) || campoIp.text.toString().trim().isNotEmpty()
        if (prefs.getBoolean("activo", false) && tieneCamara() && hayConexion) {
            iniciarServicio()
        }
    }

    override fun onStart() {
        super.onStart()
        EstadoCamara.oyente = { runOnUiThread { refrescarEstado() } }
        refrescarEstado()
    }

    override fun onStop() {
        EstadoCamara.oyente = null
        super.onStop()
    }

    /** Pinta el semáforo, el texto y el botón grande según lo que está haciendo la cámara. */
    private fun refrescarEstado() {
        val fase = EstadoCamara.fase
        val detalle = EstadoCamara.detalle
        val luzActiva = when (fase) {
            Fase.TRANSMITIENDO -> 2
            Fase.CONECTANDO, Fase.PAUSA -> 1
            else -> 0
        }
        pintarLuz(luzRoja, ROJO, luzActiva == 0)
        pintarLuz(luzAmbar, AMBAR, luzActiva == 1)
        pintarLuz(luzVerde, VERDE, luzActiva == 2)
        textoEstado.text = when (fase) {
            Fase.DETENIDA -> "Cámara detenida"
            Fase.CONECTANDO -> detalle.ifEmpty { "Conectando con la computadora…" }
            Fase.TRANSMITIENDO -> detalle.ifEmpty { "Transmitiendo" }
            Fase.PAUSA -> detalle.ifEmpty { "En pausa" }
            Fase.ERROR -> detalle.ifEmpty { "Hay un problema" }
        }
        val encendida = fase != Fase.DETENIDA
        botonPrincipal.text = if (encendida) "■  Detener cámara" else "▶  Encender cámara"
        botonPrincipal.background = fondo(if (encendida) ROJO else VERDE)

        val nombre = cartelNombre
        if (nombre != null && fase == Fase.TRANSMITIENDO) {
            cartel.text = "✓ Vinculada como «$nombre». La cámara está encendida y transmitiendo."
            cartelNombre = null
            manejador.postDelayed({ cartel.visibility = View.GONE }, 9000)
        }
    }

    private fun mostrarCartel(nombre: String) {
        cartelNombre = nombre
        cartel.text = "✓ Vinculada como «$nombre». Encendiendo la cámara…"
        cartel.visibility = View.VISIBLE
    }

    private fun actualizarTarjeta() {
        val p = prefs()
        if (Vinculo.vinculada(this)) {
            tarjeta.text = "● Vinculada como «${p.getString("v_nombre", "")}»\n" +
                "Computadora: ${p.getString("v_host", "")}  (conexión cifrada)"
            botonOlvidar.visibility = View.VISIBLE
        } else {
            tarjeta.text = "● Sin vincular\nEscanea el QR que muestra MeCam en la computadora."
            botonOlvidar.visibility = View.GONE
        }
    }

    private fun lanzarEscaner() {
        val opciones = ScanOptions()
            .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
            .setPrompt("Apunta al QR que muestra MeCam en la computadora")
            .setBeepEnabled(false)
            .setOrientationLocked(false)
        escanear.launch(opciones)
    }

    private fun vincularConQr(texto: String) {
        val datos = Vinculo.parsear(texto)
        if (datos == null) {
            estado.text = "Ese QR no es de MeCam. Escanea el que muestra el centro de control en la computadora."
            return
        }
        val mismaComputadora = Vinculo.vinculada(this) && Vinculo.huellaGuardada(this) == datos.huella
        if (mismaComputadora && Vinculo.hostGuardado(this) == datos.host) {
            // Ya está vinculado a esta computadora: se avisa en vez de crear un dispositivo duplicado
            val nombre = prefs().getString("v_nombre", "") ?: ""
            AlertDialog.Builder(this)
                .setTitle("Este celular ya está vinculado")
                .setMessage(
                    "Ya figura como «$nombre» en esa computadora, así que no hace falta escanear otra vez.\n\n" +
                        "Si lo vinculas de nuevo, se renueva el mismo dispositivo: no se crea un duplicado."
                )
                .setPositiveButton("Cancelar", null)
                .setNegativeButton("Volver a vincular") { _, _ -> hacerVinculo(datos, Vinculo.credencialActual(this)) }
                .show()
            return
        }
        // Misma computadora con otra dirección (cambió la IP): se renueva sin duplicar. Otra computadora: vínculo nuevo.
        hacerVinculo(datos, if (mismaComputadora) Vinculo.credencialActual(this) else null)
    }

    private fun hacerVinculo(datos: Vinculo.Datos, previo: String?) {
        stopService(Intent(this, CamaraService::class.java))
        EstadoCamara.poner(Fase.DETENIDA, "Detenida")
        estado.text = "Vinculando…"
        Thread {
            val r = Vinculo.vincular(this, datos, previo)
            runOnUiThread {
                actualizarTarjeta()
                if (r.ok) {
                    estado.text = ""
                    mostrarCartel(r.mensaje)
                    Toast.makeText(this, "✓ Vinculada como «${r.mensaje}»", Toast.LENGTH_LONG).show()
                    prefs().edit().putBoolean("activo", true).apply()
                    pedir()      // la cámara se enciende sola al vincular
                } else {
                    estado.text = r.mensaje
                }
            }
        }.start()
    }

    private fun olvidar() {
        detener()
        Vinculo.olvidar(this)
        actualizarTarjeta()
        estado.text = "Esta cámara ya no está vinculada. Escanea un QR nuevo para volver a vincularla."
    }

    private fun detener() {
        stopService(Intent(this, CamaraService::class.java))
        prefs().edit().putBoolean("activo", false).apply()
        EstadoCamara.poner(Fase.DETENIDA, "Detenida")
    }

    private fun revisarActualizacion() {
        Thread {
            val ultima = Actualizador.ultimaVersion()
            val actual = Actualizador.versionInstalada(this)
            if (ultima != null && ultima > actual) {
                runOnUiThread {
                    botonActualizar.text = "Actualizar MeCam a la versión $ultima"
                    botonActualizar.visibility = View.VISIBLE
                }
            }
        }.start()
    }

    private fun actualizar() {
        estado.text = "Descargando la versión nueva..."
        Thread {
            val error = Actualizador.descargarEInstalar(this)
            runOnUiThread {
                estado.text = error ?: "Confirma la instalación en la ventana que aparece."
            }
        }.start()
    }

    private fun pedir() {
        if (!Vinculo.vinculada(this) && campoIp.text.toString().trim().isEmpty()) {
            estado.text = "Primero escanea el QR de la computadora."
            return
        }
        val lista = mutableListOf(Manifest.permission.CAMERA)
        if (Build.VERSION.SDK_INT >= 33) lista.add(Manifest.permission.POST_NOTIFICATIONS)
        pedirPermisos.launch(lista.toTypedArray())
    }

    private fun iniciarServicio() {
        val ip = campoIp.text.toString().trim()
        val nombre = campoNombre.text.toString().trim().ifEmpty { "celular1" }
        val fps = (campoFps.text.toString().toIntOrNull() ?: 10).coerceIn(1, 25)
        val orientacion = campoOrientacion.selectedItemPosition
        prefs().edit()
            .putString("ip", ip)
            .putString("nombre", nombre)
            .putInt("fps", fps)
            .putInt("orientacion", orientacion)
            .putBoolean("activo", true)
            .apply()
        val intent = Intent(this, CamaraService::class.java)
            .putExtra("ip", ip)
            .putExtra("nombre", nombre)
            .putExtra("fps", fps)
            .putExtra("orientacion", orientacion)
        if (EstadoCamara.fase == Fase.DETENIDA) EstadoCamara.poner(Fase.CONECTANDO, "Iniciando…")
        ContextCompat.startForegroundService(this, intent)
        estado.text = ""
    }
}
