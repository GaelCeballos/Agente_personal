 # Smart Agent Backend

Plataforma API REST y aplicación de consola para un Agente Inteligente personal, construido con Python, FastAPI y LM-Studio para recibr, procesar y estructurar datos de tareas, notas y recordatorios en tiempo real a través de un Bot de Telegram o WhatsApp.

## Stack Tecnológico

| Capa | Tecnología |
| :--- | :--- |
| **Backend / API** | Python 3.13.x + FastAPI |
| **Procesamiento IA** | (Modelos LLM Locales) |
| **Base de Datos** | PostgreSQL 15 (Alpine) |
| **Orquestación** | Docker + Docker Compose |
| **Integración** | Telegram Bot API (Webhooks / Uvicorn) |

---

## Requisitos Previos

* **Docker Desktop** instalado y ejecutándose en el sistema.
* **Git** instalado.
* **LM-Studio** configurado y corriendo con el modelo correspondiente (ej. gemma).
* Un **Token de Bot de Telegram** activo (obtenido mediante BotFather).
* Un túnel HTTP activo (ej. **Ngrok**) para la exposición local del Webhook en desarrollo.

*⚠️ **Nota Importante:** Asegúrate de configurar correctamente tu archivo de variables de entorno `.env` en la raíz del proyecto antes de levantar los contenedores para garantizar que las credenciales de la base de datos y los tokens de API coincidan.*

---

## Gestión y Ejecución

El proyecto está completamente contenedorizado para facilitar su despliegue y desarrollo local:

| Comando | Propósito |
| :--- | :--- |
| `docker compose up --build -d` | Construye las imágenes y levanta los servicios en segundo plano. |
| `docker compose down` | Apaga y destruye los contenedores manteniendo la persistencia de datos. |
| `docker compose logs -f agent_api` | Monitorea en tiempo real las predicciones y registros de la IA. |

---

## Estrategia de Ramas

| Rama | Propósito |
| :--- | :--- |
| `main` | Producción |
| `staging` | QA / Pre-producción |
| `develop` | Integración continua |
| `feature/*` | Nuevas funcionalidades |
| `bugfix/*` | Correcciones no críticas |
| `hotfix/*` | Correcciones urgentes en producción |

### 🚦 Ambientes
`feature/*` \| `bugfix/*` \| `hotfix/*` ➔ `develop` ➔ `staging` ➔ `main`

* **develop:** integración continua, base estable para el desarrollo de nuevas características.
* **staging:** ambiente de pruebas y control de calidad (QA) previo al despliegue masivo.
* **main:** producción, contiene el código estable y funcional desplegado para el usuario final.
