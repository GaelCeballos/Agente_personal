import os
import json
import requests
from datetime import datetime

class OllamaClient:
    def __init__(self):
        self.endpoint = os.environ.get("OLLAMA_ENDPOINT")
        self.model_name = os.environ.get("OLLAMA_MODEL")
        
        self.system_prompt_analisis = (
            "Eres un secretario personal inteligente. Tu tarea es interpretar los mensajes del usuario y estructurarlos en un formato JSON estricto.\n\n"
            "=== CLAVES DEL JSON ===\n"
            "- \"intencion\": (\"guardar\", \"modificar\", \"consultar\", \"sistema\")\n"
            "- \"tipo\": (\"tarea\", \"recordatorio\", \"nota\")"
            "- \"operacion\": (\"crear\", \"actualizar\", \"eliminar\", \"completar\", \"historial\")\n"
            "- \"descripcion_limpia\": El texto principal filtrado. Extrae el nombre de la acción omitiendo palabras como 'actualiza', 'borra', 'terminé' o los porcentajes. Si quiere eliminar TODO lo de una fecha, pon exactamente \"por_fecha\".\n"
            "- \"importancia\": (1, 2, 3 o null)\n"
            "- \"progreso\": (0 a 100 o null)\n"
            "- \"fecha_recordatorio\": (Formato \"YYYY-MM-DD HH:MM:SS\" o null). Calcula el día relativo basándote en la Fecha de Referencia.\n"
            "- \"minutos_aviso\": (entero o 0)\n"
            "- \"periodo\": (\"dia\", \"semana\", \"año\" o null) - Llena esto únicamente en operaciones de historial.\n\n"
            "=== REGLAS CRÍTICAS DE OPERACIÓN ===\n"
            "1. HISTORIAL: Usa 'historial' ÚNICAMENTE si el usuario pide de forma explícita ver su pasado, cosas ya hechas, concluidas, terminadas, o solicita la palabra exacta 'historial'.\n"
            "2. CONSULTA ACTIVA: Si el usuario dice 'dame mis tareas', 'qué pendientes tengo', 'ver mis notas' o similares, busca las que están vigentes; por lo tanto, NO uses 'historial', pon operacion='crear' (o una operación de consulta estándar).\n"
            "3. COMPLETAR/TERMINAR: Si el usuario dice 'ya terminé la tarea X', 'completé', 'hice', pon intencion='modificar' y operacion='completar'.\n"
            "4. ACTUALIZAR PROGRESO: Si pide cambiar porcentaje o nivel, pon intencion='modificar', operacion='actualizar', escribe el nuevo número en 'progreso'.\n"
            "5. ELIMINAR/BORRAR: Si pide eliminar o borrar algo, pon intencion='modificar' y operacion='eliminar'.\n"
            "6. SALUDOS O CHARLA CASUAL: Si el usuario solo saluda (ej. 'hola', 'buenos días'), se despide o conversa sin pedir acciones, pon intencion='sistema'.\n"
            "Responde ÚNICAMENTE el objeto JSON plano puro, sin bloques de código markdown ni texto adicional."
        )

        self.system_prompt_consulta = (
            "Eres un secretario personal inteligente. Responde a las preguntas de manera amable, CONCISA y MUY BREVE basándote estrictamente en los registros proporcionados.\n"
            "Si el contexto indica que es un saludo o interacción casual, responde con un saludo recíproco y cordial de forma muy concisa.\n\n"
            "=== REGLAS DE FORMATO ESTRICTAS (MÁXIMA PRIORIDAD) ===\n"
            "1. PROHIBIDAS las etiquetas HTML de listas o bloques web (NUNCA uses <ul>, <li>, <p>, <br>).\n"
            "2. PROHIBIDO el markdown con asteriscos o guiones (** o -).\n"
            "3. Usa SOLAMENTE <b> para negritas, <i> para cursivas y <code> para textos fijos.\n"
            "4. ESTRICTAMENTE PROHIBIDO usar estilos o atributos web.\n"
            "5. Usa saltos de línea normales ejecutando un Enter real en el texto para separar las líneas."
        )

    def _hacer_peticion(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,
            "stream": False
        }
        try:
            response = requests.post(self.endpoint, json=payload, timeout=120)
            response.raise_for_status()
            content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
            return content.strip() if content else ""
        except Exception as e:
            print(f"❌ Error en conexión con LM Studio/Ollama: {e}")
            return ""

    def analizar_comando(self, texto_usuario: str, nombre_usuario: str = "Usuario") -> dict:
        texto_normalizado = texto_usuario.strip().lower().replace(".", "").replace("!", "").replace("¿", "").replace("?", "")
        saludos = ["hola", "buenos dias", "buenas tardes", "buenas noches", "buenas", "que tal", "hello", "hi", "saludos"]
        if texto_normalizado in saludos:
            return {"intencion": "sistema", "tipo": "nota", "operacion": "crear", "descripcion_limpia": texto_usuario}

        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_prompt = (
            f"Nombre del usuario: {nombre_usuario}\n"
            f"Fecha de Referencia Actual: {fecha_actual}\n"
            f"Mensaje del usuario: {texto_usuario}"
        )
        
        raw_text = self._hacer_peticion(self.system_prompt_analisis, user_prompt)
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(raw_text)
        except Exception as e:
            print(f"⚠️ Error parseando JSON: {e} -> Recibido: {raw_text}")
            return {"intencion": "sistema", "tipo": "nota", "operacion": "crear"}

    def responder_consulta(self, pregunta_usuario: str, contexto_db: str, nombre_usuario: str = "Usuario") -> str:
        user_prompt = (
            f"Nombre del usuario: {nombre_usuario}\n"
            f"Registros actuales de la Base de Datos o Contexto:\n{contexto_db}\n\n"
            f"Consulta del usuario: {pregunta_usuario}"
        )
        return self._hacer_peticion(self.system_prompt_consulta, user_prompt)