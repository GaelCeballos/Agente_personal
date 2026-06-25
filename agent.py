# Modificación sobre tu archivo agent.py existente
import sys
import re
from datetime import datetime, timedelta
from database import DatabaseManager
from llm import OllamaClient


TIPOS_VALIDOS = ["tarea", "recordatorio", "nota"] 

class AgentApp:
    def __init__(self):
        self.db = DatabaseManager()
        self.ai = OllamaClient()

    def ejecutar(self, argumentos: list):
        if not argumentos:
            self._menu()
            return

        comando = " ".join(argumentos).strip()
        datos = self.ai.analizar_comando(comando)
        if not datos:
            print("⚠️ No pude procesar la solicitud con Ollama.")
            return

        intencion = datos.get("intencion")
        tipo = datos.get("tipo", "nota")
        operacion = datos.get("operacion", "crear")
        descripcion = datos.get("descripcion_limpia", comando)
        importancia = datos.get("importancia")
        progreso = datos.get("progreso", 0)
        fecha_rec = datos.get("fecha_recordatorio")
        minutos_aviso = datos.get("minutos_aviso", 0)
        periodo = datos.get("periodo")

        if any(x in comando.lower() for x in ["ayer", "hoy", "mañana"]):
            if any(verb in comando.lower() for verb in ["elimina", "borra", "limpia", "quita"]):
                operacion = "eliminar_fecha"
                if "ayer" in comando.lower():
                    fecha_rec = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
                elif "hoy" in comando.lower():
                    fecha_rec = datetime.now().strftime("%Y-%m-%d 00:00:00")

        match_porcentaje = re.search(r'(\d+)\s*%', comando)
        if match_porcentaje and any(w in comando.lower() for w in ["actualiza", "progreso", "nivel"]):
            intencion = "modificar"
            operacion = "actualizar"
            tipo = "tarea"
            progreso = int(match_porcentaje.group(1))

        if intencion == "sistema":
            print(self.ai.responder_consulta(comando, "Consola CLI: El usuario te está saludando o hablando de forma casual."))
            return

        elif intencion == "consultar":
            if operacion == "historial":
                contexto = self.db.obtener_historial("cli", periodo)
            elif tipo in TIPOS_VALIDOS:
                contexto = self.db.obtener_resumen_por_tipo("cli", tipo)
            else:
                contexto = self.db.obtener_resumen_completo("cli")
            print(self.ai.responder_consulta(comando, contexto))
            return

        elif intencion in ["guardar", "modificar"]:
            if operacion == "eliminar":
                borrados = self.db.eliminar_registro("cli", tipo, descripcion)
                if borrados: print(f"\n🗑️  [{tipo.upper()}] Eliminado de la base de datos: '{descripcion}'\n")
                else: print(f"\n⚠️ No encontré ningún(a) {tipo} activo con '{descripcion}'\n")
            
            elif operacion == "completar":
                completados = self.db.completar_registro("cli", tipo, descripcion)
                if completados: print(f"\n✅ [{tipo.upper()}] Marcado como completado con éxito: '{descripcion}'\n")
                else: print(f"\n⚠️ No encontré ningún(a) {tipo} activo con '{descripcion}'\n")

            elif operacion == "eliminar_fecha":
                fecha_solo = fecha_rec.split()[0] if fecha_rec else None
                if fecha_solo:
                    borrados = self.db.eliminar_por_fecha("cli", tipo, fecha_solo)
                    print(f"\n🗑️ Se eliminaron permanentemente {borrados} {tipo}s del día {fecha_solo}.\n")
                else: print("\n⚠️ No pude procesar la fecha para eliminar.\n")
                    
            else:
                f_rec_parsed = None
                if fecha_rec:
                    try: f_rec_parsed = datetime.strptime(fecha_rec, "%Y-%m-%d %H:%M:%S")
                    except: f_rec_parsed = None

                resultado, desc_final, prog_final, f_rec = self.db.registrar_o_actualizar(
                    "cli", tipo, operacion, descripcion, importancia, progreso, f_rec_parsed, minutos_aviso
                )

                if tipo == "tarea":
                    barra = "█" * (prog_final // 10) + "░" * (10 - prog_final // 10)
                    if prog_final == 100:
                        print(f"\n✅ [TAREA] ¡Al 100%! Movida al historial: {desc_final}\n")
                    else:
                        accion_txt = "Actualizada" if resultado == "actualizado" else "Guardada"
                        print(f"\n✅ [TAREA] {accion_txt} y Vigente: {desc_final}")
                        print(f"   [{barra}] {prog_final}%\n")
                elif tipo == "recordatorio" and f_rec:
                    print(f"\n⏰ [RECORDATORIO] Programado para el {f_rec.strftime('%d/%m/%Y %H:%M')}: {desc_final}\n")
                else:
                    imp_str = f" (Prioridad {importancia})" if importancia else ""
                    print(f"\n📓 [{tipo.upper()}] Guardado{imp_str}: {desc_final}\n")
            return

    def _menu(self):
        print("\n🤖 AGENT Consola Inteligente — Ejemplos:")
        print("  agent hola bot")
        print("  agent cuánto dinero tengo en el banco?")
        print("  agent balance de mis cuentas")
        print("  agent qué cosas tengo pendientes?\n")

if __name__ == "__main__":
    app = AgentApp()
    app.ejecutar(sys.argv[1:])