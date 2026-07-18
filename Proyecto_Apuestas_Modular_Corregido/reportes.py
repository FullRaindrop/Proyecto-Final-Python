import pandas as pd

from utilidades import BASE_DIR, EstadoSistema, logger


def generar_reportes(estado: EstadoSistema) -> None:
    print("\n--- GENERAR REPORTES EXCEL ---")
    try:
        datos_usuarios = [
            {
                "Nombre": u.nombre,
                "Apellido": u.apellido,
                "Correo": u.correo,
                "Edad": u.edad,
                "Saldo": round(u.saldo, 2),
            }
            for u in estado.usuarios.values()
        ]
        columnas_apuestas = [
            "id", "fecha", "usuario", "equipo_local", "equipo_visitante",
            "pronostico", "monto", "cuota", "estado",
            "ganancia_bruta", "ganancia_neta",
        ]
        columnas_pagos = ["fecha", "usuario", "tipo", "metodo", "monto"]

        ganancias = [
            {
                "ID Apuesta": a["id"],
                "Usuario": a["usuario"],
                "Partido": f"{a['equipo_local']} vs {a['equipo_visitante']}",
                "Estado": a["estado"],
                "Monto Apostado": a["monto"],
                "Premio Bruto": a.get("ganancia_bruta", 0),
                "Ganancia o Pérdida Neta": a.get("ganancia_neta", 0),
            }
            for a in estado.apuestas if a.get("estado") != "Pendiente"
        ]
        ganadores = [
            {
                "ID Apuesta": a["id"],
                "Usuario": a["usuario"],
                "Partido": f"{a['equipo_local']} vs {a['equipo_visitante']}",
                "Pronóstico": a["pronostico"],
                "Monto Apostado": a["monto"],
                "Cuota": a["cuota"],
                "Premio Bruto": a.get("ganancia_bruta", 0),
                "Ganancia Neta": a.get("ganancia_neta", 0),
            }
            for a in estado.apuestas if a.get("estado") == "Ganada"
        ]

        archivos = {
            "usuarios.xlsx": pd.DataFrame(datos_usuarios),
            "apuestas.xlsx": pd.DataFrame(estado.apuestas, columns=columnas_apuestas),
            "pagos.xlsx": pd.DataFrame(estado.pagos, columns=columnas_pagos),
            "ganancias.xlsx": pd.DataFrame(ganancias),
            "ganadores.xlsx": pd.DataFrame(ganadores),
        }
        for nombre, dataframe in archivos.items():
            dataframe.to_excel(BASE_DIR / nombre, index=False)

        logger.info("Reportes Excel generados correctamente")
        print("Reportes generados en la carpeta del proyecto:")
        for nombre in archivos:
            print(f"- {nombre}")
    except ImportError as error:
        logger.error("Falta biblioteca Excel: %s", error)
        print("Instale las bibliotecas con: pip install pandas openpyxl")
    except PermissionError:
        logger.error("Archivo Excel abierto durante la generación")
        print("Cierre los archivos Excel abiertos e inténtelo nuevamente.")
    except Exception as error:
        logger.exception("Error al generar reportes: %s", error)
        print(f"No se pudieron generar los reportes: {error}")
