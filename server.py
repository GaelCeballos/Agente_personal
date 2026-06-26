
import os
import re
import json
import requests
import asyncio 
from contextlib import asynccontextmanager 
from fastapi import FastAPI, Request, BackgroundTasks
from database import DatabaseManager
from llm import OllamaClient
 
from datetime import datetime, timedelta

app = FastAPI()
db = DatabaseManager()
ai = OllamaClient()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
clean_token = TELEGRAM_TOKEN.strip("[]") if TELEGRAM_TOKEN else ""
TELEGRAM_API_URL = f"https://api.telegram.org/bot{clean_token}"

TIPOS_VALIDOS = ["tarea", "recordatorio", "nota"]

def obtener_nombre_usuario(chat_id: str) -> str:
    try:
        with open('user.json', 'r') as f:
            datos = json.load(f)
            return datos.get("users", {}).get(str(chat_id))
    except Exception: return None

async def revisor_recordatorios():
    while True:
        try:
            pendientes = db.obtener_recordatorios_pendientes()
            for req in pendientes:
                reg_id, chat_id, descripcion, fecha_rec = req
                mensaje_alerta = f"🔔 <b>¡RECORDATORIO!</b>\n\nEs hora de: <i>{descripcion}</i>"
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={"chat_id": chat_id, "text": mensaje_alerta, "parse_mode": "HTML"})
        except Exception as e:
            print(f"Error revisando recordatorios: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(revisor_recordatorios())
    yield
    task.cancel()

app.router.lifespan_context = lifespan

def enviar_telegram(chat_id: int, texto: str):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    try: requests.post(url, json=payload)
    except Exception as e: print(f"❌ Error enviando a Telegram: {e}")

def barra_progreso(porcentaje: int) -> str:
    if porcentaje is None: porcentaje = 0
    bloques = max(0, min(10, porcentaje // 10))
    return "█" * bloques + "░" * (10 - bloques)

async def procesar_logica_ia(chat_id: int, texto_usuario: str):
    try:
        nombre = obtener_nombre_usuario(str(chat_id)) or "Usuario"
        datos = ai.analizar_comando(texto_usuario, nombre)
        
        intencion = datos.get("intencion", "sistema")
        tipo = datos.get("tipo", "nota")
        operacion = datos.get("operacion", "crear")
        descripcion = datos.get("descripcion_limpia", texto_usuario)
        importancia = datos.get("importancia")
        progreso = datos.get("progreso", 0)
        fecha_rec = datos.get("fecha_recordatorio")
        minutos_aviso = datos.get("minutos_aviso", 0)
        periodo = datos.get("periodo")

        if any(x in texto_usuario.lower() for x in ["ayer", "hoy", "mañana"]):
            if any(verb in texto_usuario.lower() for verb in ["elimina", "borra", "limpia", "quita"]):
                operacion = "eliminar_fecha"
                if "ayer" in texto_usuario.lower():
                    fecha_rec = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
                elif "hoy" in texto_usuario.lower():
                    fecha_rec = datetime.now().strftime("%Y-%m-%d 00:00:00")

        match_porcentaje = re.search(r'(\d+)\s*%', texto_usuario)
        if match_porcentaje and any(w in texto_usuario.lower() for w in ["actualiza", "progreso", "nivel"]):
            intencion = "modificar"
            operacion = "actualizar"
            tipo = "tarea"
            progreso = int(match_porcentaje.group(1))

        if not descripcion:
            descripcion = texto_usuario

        respuesta = ""

        if operacion == "historial" or intencion == "sistema" or intencion == "consultar":
            if operacion == "historial":
                contexto_db = db.obtener_historial(str(chat_id), periodo)
            elif intencion == "sistema":
                contexto_db = "El usuario te está saludando o haciendo una interacción social casual. Responde cordialmente."
            else:
                contexto_db = db.obtener_resumen_completo(str(chat_id))
            
            respuesta = ai.responder_consulta(texto_usuario, contexto_db, nombre)
        
        else:
            if operacion == "eliminar":
                borrados = db.eliminar_registro(str(chat_id), tipo, descripcion)
                respuesta = f"🗑️ <b>[{tipo.upper()}]</b> Eliminado permanentemente: <i>{descripcion}</i>" if borrados > 0 else f"⚠️ No encontré: <i>{descripcion}</i>"
            
            elif operacion == "completar":
                completados = db.completar_registro(str(chat_id), tipo, descripcion)
                respuesta = f"✅ <b>[{tipo.upper()}]</b> Marcado como completado: <i>{descripcion}</i>" if completados > 0 else f"⚠️ No encontré esa {tipo} activa."

            elif operacion == "eliminar_fecha":
                fecha_solo = fecha_rec.split()[0] if fecha_rec else None
                if fecha_solo:
                    borrados = db.eliminar_por_fecha(str(chat_id), tipo, fecha_solo)
                    respuesta = f"🗑️ <b>[{tipo.upper()}]</b> Se eliminaron permanentemente {borrados} registros del día {fecha_solo}."
                else: respuesta = "⚠️ No determiné la fecha."
            
            else:
                f_rec_parsed = None
                if fecha_rec:
                    try: f_rec_parsed = datetime.strptime(fecha_rec, "%Y-%m-%d %H:%M:%S")
                    except: f_rec_parsed = None

                resultado, desc_final, prog_final, _ = db.registrar_o_actualizar(
                    str(chat_id), tipo, operacion, descripcion, importancia, progreso, f_rec_parsed, minutos_aviso=minutos_aviso
                )
                
                if tipo == "recordatorio": 
                    respuesta = f"⏰ <b>[RECORDATORIO]</b>: <i>{desc_final}</i>"
                elif tipo == "tarea":
                    barra = barra_progreso(prog_final)
                    if prog_final == 100: 
                        respuesta = f"✅ <b>[TAREA]</b> ¡Al 100%! Movida al historial: <i>{desc_final}</i>"
                    else: 
                        respuesta = f"✅ <b>[TAREA]</b> Guardada/Vigente:\n  <i>{desc_final}</i>\n  <code>[{barra}] {prog_final}%</code>"
                else: 
                    respuesta = f"📓 <b>[NOTA]</b> Guardada: <i>{desc_final}</i>"

        enviar_telegram(chat_id, respuesta)
    except Exception as e: print(f"❌ Error en lógica IA: {e}")

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            texto_usuario = data["message"].get("text", "").strip()
            if texto_usuario: background_tasks.add_task(procesar_logica_ia, chat_id, texto_usuario)
            return {"status": "ok"}
        return {"status": "no text"}
    except Exception as e: return {"status": "error", "detail": str(e)}