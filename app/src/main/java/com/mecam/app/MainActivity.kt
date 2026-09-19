package com.mecam.app

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

class MainActivity : ComponentActivity() {

    private lateinit var campoIp: EditText
    private lateinit var campoNombre: EditText
    private lateinit var campoFps: EditText
    private lateinit var campoOrientacion: Spinner
    private lateinit var botonActualizar: Button
    private lateinit var botonOlvidar: Button
    private lateinit var tarjeta: TextView
    private lateinit var ajustes: LinearLayout
    private lateinit var estado: TextView

    private val pedirPermisos = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { _ ->
        if (tieneCamara()) {
            iniciarServicio()
        } else {
            estado.text = "Falta el permiso de cámara. Toca Iniciar y elige Permitir."
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = prefs()
        val pad = (20 * resources.displayMetrics.density).toInt()

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
        tarjeta = TextView(this).apply {
            textSize = 16f
            setPadding(0, pad / 2, 0, pad / 2)
        }
        val botonQr = Button(this).apply {
            text = "Escanear QR para vincular"
            textSize = 18f
            setOnClickListener { lanzarEscaner() }
        }
        val botonIniciar = Button(this).apply {
            text = "Iniciar cámara"
            setOnClickListener { pedir() }
        }
        val botonDetener = Button(this).apply {
            text = "Detener"
            setOnClickListener {
                stopService(Intent(this@MainActivity, CamaraService::class.java))
                prefs.edit().putBoolean("activo", false).apply()
                estado.text = "Detenida."
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
            setPadding(0, pad, 0, 0)
        }

        listOf(titulo, botonActualizar, tarjeta, botonQr, botonIniciar, botonDetener, botonAjustes, ajustes, estado)
            .forEach { raiz.addView(it) }
        setContentView(ScrollView(this).apply { addView(raiz) })

        actualizarTarjeta()
        revisarActualizacion()

        // Si la cámara estaba encendida (por ejemplo antes de actualizar), se reanuda al abrir la app
        val hayConexion = Vinculo.vinculada(this) || campoIp.text.toString().trim().isNotEmpty()
        if (prefs.getBoolean("activo", false) && tieneCamara() && hayConexion) {
            iniciarServicio()
        }
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
            estado.text = "Ese QR no es de MeCam. Escanea el que muestra la ventana de MeCam en la computadora."
            return
        }
        stopService(Intent(this, CamaraService::class.java))
        estado.text = "Vinculando…"
        Thread {
            val r = Vinculo.vincular(this, datos)
            runOnUiThread {
                estado.text = if (r.ok) {
                    "¡Listo! Vinculada como «${r.mensaje}». Toca Iniciar cámara."
                } else {
                    r.mensaje
                }
                actualizarTarjeta()
            }
        }.start()
    }

    private fun olvidar() {
        stopService(Intent(this, CamaraService::class.java))
        Vinculo.olvidar(this)
        actualizarTarjeta()
        estado.text = "Esta cámara ya no está vinculada. Escanea un QR nuevo para volver a vincularla."
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
        ContextCompat.startForegroundService(this, intent)
        estado.text = "Cámara iniciada. Ya puedes apagar la pantalla."
    }
}
