import os
import psycopg2
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        host = os.environ.get('DB_HOST')
        port = os.environ.get('DB_PORT')
        dbname = os.environ.get('DB_NAME')
        user = os.environ.get('DB_USER')
        password = os.environ.get('DB_PASSWORD', 'gael_password')

        self.conn_string = f"host={host} dbname={dbname} user={user} password={password} port={port}"
        self._init_db()
    
    def _get_connection(self):
        return psycopg2.connect(self.conn_string)
    
    def _init_db(self):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS tipos_accion (
                                    id SERIAL PRIMARY KEY,
                                    nombre VARCHAR(50) UNIQUE NOT NULL)''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS registros (
                                    id SERIAL PRIMARY KEY,
                                    tipo_id INT REFERENCES tipos_accion(id),
                                    telefono VARCHAR(20) NOT NULL, 
                                    descripcion TEXT NOT NULL,
                                    importancia INT,
                                    progreso INT DEFAULT 0,
                                    fecha_recordatorio TIMESTAMP DEFAULT NULL,
                                    minutos_aviso INT DEFAULT 0,
                                    notificado BOOLEAN DEFAULT FALSE,
                                    activo BOOLEAN DEFAULT TRUE,
                                    completado BOOLEAN DEFAULT FALSE,
                                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
                
                cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS minutos_aviso INT DEFAULT 0;")
                cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS notificado BOOLEAN DEFAULT FALSE;")
                cursor.execute("ALTER TABLE registros ADD COLUMN IF NOT EXISTS completado BOOLEAN DEFAULT FALSE;")
            conn.commit()

    def _obtener_o_crear_tipo(self, nombre_tipo: str) -> int:
        nombre_limpio = nombre_tipo.strip().lower()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM tipos_accion WHERE nombre = %s", (nombre_limpio,))
                resultado = cursor.fetchone()
                if resultado:
                    return resultado[0]
                
                cursor.execute("INSERT INTO tipos_accion (nombre) VALUES (%s) RETURNING id", (nombre_limpio,))
                nuevo_id = cursor.fetchone()[0]
            conn.commit()
            return nuevo_id

    def _crear_patron_busqueda(self, texto: str) -> str:
        texto = texto.lower()
        for c in [',', '.', '!', '?', '-', '_', '`']:
            texto = texto.replace(c, ' ')
        palabras = texto.split()
        excluir = {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'a', 'en', 'para', 'mi', 'mis', 'con', 'del', 'al', 'actualiza', 'progreso'}
        filtradas = [p for p in palabras if p not in excluir]
        if not filtradas:
            return f"%{texto.strip()}%"
        return f"%{'%'.join(filtradas)}%"

    def registrar_o_actualizar(self, telefono: str, tipo: str, operacion: str, descripcion: str, importancia: int, progreso: int = 0, fecha_rec: str = None, minutos_aviso: int = 0) -> tuple:
        tipo_id = self._obtener_o_crear_tipo(tipo)
        now = datetime.now()

        f_rec_parsed = None
        if isinstance(fecha_rec, datetime):
            f_rec_parsed = fecha_rec
        elif fecha_rec and str(fecha_rec).strip().lower() not in ["none", "null", ""]:
            try: f_rec_parsed = datetime.strptime(fecha_rec, "%Y-%m-%d %H:%M:%S")
            except ValueError: f_rec_parsed = None

        es_100 = (progreso == 100)
        nuevo_activo = False if es_100 else True
        nuevo_completado = True if es_100 else False

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                if operacion == 'actualizar' or tipo.lower() == 'tarea':
                    patron = self._crear_patron_busqueda(descripcion)
                    cursor.execute("""SELECT id, descripcion, progreso FROM registros 
                                      WHERE tipo_id = %s AND telefono = %s AND (descripcion ILIKE %s OR %s ILIKE CONCAT('%%', descripcion, '%%')) AND activo = TRUE
                                      LIMIT 1""", (tipo_id, telefono, patron, descripcion))
                    existe = cursor.fetchone()

                    if existe:
                        registro_id = existe[0]
                        desc_existente = existe[1]
                        cursor.execute("""UPDATE registros SET progreso = %s, importancia = COALESCE(%s, importancia), 
                                          fecha_recordatorio = COALESCE(%s, fecha_recordatorio), minutos_aviso = %s, notificado = FALSE,
                                          activo = %s, completado = %s
                                          WHERE id = %s""", (progreso, importancia, f_rec_parsed, minutos_aviso, nuevo_activo, nuevo_completado, registro_id))
                        conn.commit()
                        return "actualizado", desc_existente, progreso, f_rec_parsed

                cursor.execute("""INSERT INTO registros (tipo_id, telefono, descripcion, importancia, progreso, fecha_recordatorio, minutos_aviso, notificado, fecha, activo, completado) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s, %s)""", 
                               (tipo_id, telefono, descripcion, importancia, progreso, f_rec_parsed, minutos_aviso, now, nuevo_activo, nuevo_completado))
                conn.commit()
                return "creado", descripcion, progreso, f_rec_parsed

    def eliminar_registro(self, telefono: str, tipo: str, descripcion: str) -> int:
        tipo_limpio = tipo.strip().lower()
        patron_flexible = self._crear_patron_busqueda(descripcion)
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM tipos_accion WHERE nombre = %s", (tipo_limpio,))
                res = cursor.fetchone()
                if not res: return 0
                tipo_id = res[0]
                
                # AHORA SÍ ES BORRADO FÍSICO REAL (DELETE)
                cursor.execute("""DELETE FROM registros 
                                  WHERE tipo_id = %s AND telefono = %s 
                                  AND (descripcion ILIKE %s OR %s ILIKE CONCAT('%%', descripcion, '%%'))""", 
                               (tipo_id, telefono, patron_flexible, descripcion))
                borrados = cursor.rowcount
            conn.commit()
            return borrados

    def eliminar_por_fecha(self, telefono: str, tipo: str, fecha_iso: str) -> int:
        tipo_limpio = tipo.strip().lower()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM tipos_accion WHERE nombre = %s", (tipo_limpio,))
                res = cursor.fetchone()
                if not res: return 0
                tipo_id = res[0]
                
                # BORRADO FÍSICO REAL
                cursor.execute("""DELETE FROM registros 
                                  WHERE tipo_id = %s AND telefono = %s 
                                  AND (DATE(fecha_recordatorio) = %s OR DATE(fecha) = %s)""", 
                               (tipo_id, telefono, fecha_iso, fecha_iso))
                borrados = cursor.rowcount
            conn.commit()
            return borrados

    def completar_registro(self, telefono: str, tipo: str, descripcion: str) -> int:
        tipo_limpio = tipo.strip().lower()
        patron_flexible = self._crear_patron_busqueda(descripcion)
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM tipos_accion WHERE nombre = %s", (tipo_limpio,))
                res = cursor.fetchone()
                if not res: return 0
                tipo_id = res[0]
                
                # TERMINADA CON ÉXITO: activo=FALSE, completado=TRUE, progreso=100
                cursor.execute("""UPDATE registros SET activo = FALSE, completado = TRUE, progreso = 100
                                  WHERE tipo_id = %s AND telefono = %s AND activo = TRUE 
                                  AND (descripcion ILIKE %s OR %s ILIKE CONCAT('%%', descripcion, '%%'))""", 
                               (tipo_id, telefono, patron_flexible, descripcion))
                completados = cursor.rowcount
            conn.commit()
            return completados

    def eliminar_todos_por_tipo(self, telefono: str, tipo: str) -> int:
        tipo_limpio = tipo.strip().lower()
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM tipos_accion WHERE nombre = %s", (tipo_limpio,))
                res = cursor.fetchone()
                if not res: return 0
                tipo_id = res[0]
                
                # BORRADO FÍSICO MÚLTIPLE
                cursor.execute("""DELETE FROM registros 
                                  WHERE tipo_id = %s AND telefono = %s""", 
                               (tipo_id, telefono))
                borrados = cursor.rowcount
            conn.commit()
            return borrados

    def obtener_historial(self, telefono: str, periodo: str = None) -> str:
        periodo_limpio = str(periodo).strip().lower() if periodo else "todos"
        titulo = "COMPLETO"
        where_time = ""
        
        if periodo_limpio in ["dia", "día", "hoy"]:
            titulo = "DE HOY"
            where_time = "AND fecha >= CURRENT_DATE"
        elif periodo_limpio == "semana":
            titulo = "DE LA SEMANA"
            where_time = "AND fecha >= NOW() - INTERVAL '7 days'"
        elif periodo_limpio in ["ano", "año"]:
            titulo = "DEL AÑO"
            where_time = "AND fecha >= NOW() - INTERVAL '1 year'"
            
        salida = f"<b>📈 HISTORIAL DE ACTIVIDADES {titulo}</b>\n"
        salida += "─" * 25 + "\n"
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Filtrado estricto: r.completado = TRUE
                query = f"""SELECT r.descripcion, t.nombre, TO_CHAR(r.fecha, 'DD/MM/YYYY') 
                            FROM registros r
                            JOIN tipos_accion t ON r.tipo_id = t.id
                            WHERE r.telefono = %s AND r.completado = TRUE
                            {where_time}
                            ORDER BY r.fecha DESC"""
                cursor.execute(query, (telefono,))
                elementos = cursor.fetchall()
                
                if not elementos:
                    return salida + f"  _(No hay actividades completadas registradas en este periodo)_\n" + "─" * 25
                    
                for el in elementos:
                    salida += f"  ✅ [{el[1].upper()}] {el[0]} ({el[2]})\n"
        salida += "─" * 25
        return salida

    def obtener_resumen_completo(self, telefono: str) -> str:
        salida = "<b>🤖 PANEL DE CONTROL</b>\n"
        salida += "═" * 25 + "\n"
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, nombre FROM tipos_accion ORDER BY nombre")
                tipos = cursor.fetchall()
                for t_id, t_nombre in tipos:
                    # SOLO muestra aquellas donde completado = FALSE y activo = TRUE
                    cursor.execute("""SELECT descripcion, importancia, progreso, fecha_recordatorio, minutos_aviso 
                                      FROM registros 
                                      WHERE tipo_id = %s AND telefono = %s AND activo = TRUE AND completado = FALSE
                                      ORDER BY fecha DESC""", (t_id, telefono))
                    reg = cursor.fetchall()
                    if reg:
                        salida += f"\n<b>{t_nombre.upper()}:</b>\n"
                        for r in reg:
                            desc, imp, prog, f_rec, min_aviso = r
                            detalles = []
                            if imp: detalles.append(f"Prioridad {imp}")
                            if t_nombre.lower() == 'tarea': detalles.append(f"{prog}%")
                            if f_rec: 
                                f_str = f_rec.strftime('%d/%m %H:%M')
                                if min_aviso > 0: detalles.append(f"⏰ {f_str} (-{min_aviso}m)")
                                else: detalles.append(f"⏰ {f_str}")
                            detalles_str = f" ({', '.join(detalles)})" if detalles else ""
                            salida += f"  • {desc}{detalles_str}\n"
        return salida

    def obtener_resumen_por_tipo(self, telefono: str, tipo: str) -> str:
        tipo_limpio = tipo.strip().lower()
        salida = f"<b>✨ TUS {tipo_limpio.upper()}S</b>\n"
        salida += "─" * 20 + "\n"
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # SOLO muestra aquellas donde completado = FALSE y activo = TRUE
                cursor.execute("""SELECT r.descripcion, r.importancia, r.progreso 
                                  FROM registros r
                                  JOIN tipos_accion t ON r.tipo_id = t.id
                                  WHERE t.nombre = %s AND r.telefono = %s AND r.activo = TRUE AND r.completado = FALSE
                                  ORDER BY r.fecha DESC""", (tipo_limpio, telefono))
                elementos = cursor.fetchall()
                if not elementos:
                    return salida + f"  _(No tienes {tipo_limpio}s vigentes)_\n" + "─" * 20
                for el in elementos:
                    desc, imp, prog = el
                    if tipo_limpio == "tarea":
                        salida += f"  • {desc} [{imp if imp else 1}] → {prog}%\n"
                    else:
                        imp_str = f" [Nivel {imp}]" if imp else ""
                        salida += f"  • {desc}{imp_str}\n"
        salida += "─" * 20
        return salida

    def obtener_recordatorios_pendientes(self):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""SELECT id, telefono, descripcion, fecha_recordatorio 
                                  FROM registros 
                                  WHERE activo = TRUE 
                                  AND completado = FALSE
                                  AND notificado = FALSE 
                                  AND fecha_recordatorio IS NOT NULL 
                                  AND NOW() >= (fecha_recordatorio - (minutos_aviso * INTERVAL '1 minute'))""")
                pendientes = cursor.fetchall()
                if pendientes:
                    ids = tuple([p[0] for p in pendientes])
                    cursor.execute("UPDATE registros SET notificado = TRUE WHERE id IN %s", (ids,))
                    conn.commit()
                return pendientes