package com.mecam.app

/** En qué situación está la cámara. La pantalla principal lo muestra como un semáforo. */
enum class Fase { DETENIDA, CONECTANDO, TRANSMITIENDO, PAUSA, ERROR }

/** Estado compartido entre el servicio de la cámara y la pantalla principal. */
object EstadoCamara {
    @Volatile var fase: Fase = Fase.DETENIDA
    @Volatile var detalle: String = ""
    @Volatile var oyente: (() -> Unit)? = null

    fun poner(nueva: Fase, texto: String = "") {
        fase = nueva
        detalle = texto
        oyente?.invoke()
    }
}
