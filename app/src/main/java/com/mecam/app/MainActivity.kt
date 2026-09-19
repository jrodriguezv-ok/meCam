package com.mecam.app

import android.Manifest
import android.content.Context
import android.content.Intent
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

class MainActivity : ComponentActivity() {

    private lateinit var campoIp: EditText
    private lateinit var campoNombre: EditText
    private lateinit var campoFps: EditText
    private lateinit var campoOrientacion: Spinner
    private lateinit var botonActualizar: Button
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

    private fun tieneCamara() = ContextCompat.checkSelfPermission(
        this, Manifest.permission.CAMERA
    ) == PackageManager.PERMISSION_GRANTED

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences("mecam", Context.MODE_PRIVATE)
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
        campoIp = EditText(this).apply {
            hint = "IP de la computadora (ej: 192.168.1.128)"
            setText(prefs.getString("ip", ""))
        }
        campoNombre = EditText(this).apply {
            hint = "Nombre de esta cámara (ej: celular1)"
            setText(prefs.getString("nombre", "celular1"))
        }
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
        val botonBateria = Button(this).apply {
            text = "Ajustes de batería (para que no se cierre)"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
        }
        estado = TextView(this).apply {
            textSize = 16f
            setPadding(0, pad, 0, 0)
        }

        listOf(
            titulo, botonActualizar, campoIp, campoNombre, campoFps, campoOrientacion,
            botonIniciar, botonDetener, botonBateria, estado
        ).forEach { raiz.addView(it) }
        setContentView(ScrollView(this).apply { addView(raiz) })

        revisarActualizacion()

        // Si la cámara estaba encendida (por ejemplo antes de actualizar), se reanuda al abrir la app
        if (prefs.getBoolean("activo", false) && tieneCamara() &&
            campoIp.text.toString().trim().isNotEmpty()
        ) {
            iniciarServicio()
        }
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
        if (campoIp.text.toString().trim().isEmpty()) {
            estado.text = "Escribe la IP de la computadora."
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
        getSharedPreferences("mecam", Context.MODE_PRIVATE).edit()
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
