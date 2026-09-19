plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Cada compilación en GitHub sube el número de versión (necesario para poder actualizar)
val numeroCompilacion = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
val rutaClave: String? = System.getenv("MECAM_KEYSTORE")

android {
    namespace = "com.mecam.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.mecam.app"
        minSdk = 24
        targetSdk = 34
        versionCode = numeroCompilacion
        versionName = "1.0.$numeroCompilacion"
    }

    signingConfigs {
        create("mecam") {
            if (rutaClave != null && java.io.File(rutaClave).exists()) {
                storeFile = java.io.File(rutaClave)
                storeType = "pkcs12"
                storePassword = System.getenv("MECAM_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("MECAM_KEY_ALIAS")
                keyPassword = System.getenv("MECAM_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (rutaClave != null) {
                signingConfig = signingConfigs.getByName("mecam")
            }
        }
    }
    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.1")
    implementation("androidx.lifecycle:lifecycle-service:2.8.4")
    implementation("androidx.camera:camera-core:1.3.4")
    implementation("androidx.camera:camera-camera2:1.3.4")
    implementation("androidx.camera:camera-lifecycle:1.3.4")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
