from datetime import datetime

from usuarios import requiere_sesion
from utilidades import (
    EstadoSistema,
    buscar_equipo,
    clave_partido,
    guardar_estado,
    logger,
    solicitar_entero,
    solicitar_float,
    texto_comparable,
)


def mostrar_equipos(estado: EstadoSistema) -> None:
    print("\nEquipos disponibles:")
    for indice, equipo in enumerate(sorted(estado.equipos), start=1):
        print(f"{indice:2}. {equipo}")


def realizar_apuesta(estado: EstadoSistema) -> None:
    if not requiere_sesion(estado):
        return

    print("\n--- REALIZAR APUESTA ---")
    mostrar_equipos(estado)
    local = buscar_equipo(estado, input("\nEquipo local: "))
    visitante = buscar_equipo(estado, input("Equipo visitante: "))

    if local is None or visitante is None:
        print("Uno de los equipos no está registrado. Consulte primero los resultados web.")
        return
    if texto_comparable(local) == texto_comparable(visitante):
        print("El equipo local y visitante deben ser diferentes.")
        return

    print("\nSeleccione su pronóstico:")
    print(f"1. Gana {local}")
    print("2. Empate")
    print(f"3. Gana {visitante}")
    pronostico = {"1": local, "2": "Empate", "3": visitante}.get(
        input("Opción: ").strip()
    )
    if pronostico is None:
        print("Pronóstico inválido.")
        return

    monto = solicitar_float("Monto a apostar: $", 0.01)
    if monto > estado.usuario_activo.saldo:
        print("Saldo insuficiente.")
        return
    cuota = solicitar_float("Cuota de la apuesta (ejemplo 1.80): ", 1.01)

    estado.usuario_activo.saldo -= monto
    siguiente_id = max((a.get("id", 0) for a in estado.apuestas), default=0) + 1
    nueva = {
        "id": siguiente_id,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": estado.usuario_activo.correo,
        "equipo_local": local,
        "equipo_visitante": visitante,
        "pronostico": pronostico,
        "monto": round(monto, 2),
        "cuota": round(cuota, 2),
        "estado": "Pendiente",
        "ganancia_bruta": 0.0,
        "ganancia_neta": 0.0,
    }
    estado.apuestas.append(nueva)
    guardar_estado(estado)
    logger.info(
        "Apuesta ID %s por %s: %s vs %s, pronóstico %s, monto %.2f",
        siguiente_id, estado.usuario_activo.correo, local, visitante,
        pronostico, monto,
    )
    print("Apuesta registrada correctamente.")
    print(f"Saldo restante: ${estado.usuario_activo.saldo:.2f}")


def _ganador(local: str, visitante: str, goles_local: int, goles_visitante: int) -> str:
    if goles_local > goles_visitante:
        return local
    if goles_visitante > goles_local:
        return visitante
    return "Empate"


def validar_apuestas_de_partido(
    estado: EstadoSistema,
    local: str,
    visitante: str,
    goles_local: int,
    goles_visitante: int,
) -> int:
    ganador = _ganador(local, visitante, goles_local, goles_visitante)
    cantidad = 0

    for apuesta in estado.apuestas:
        mismo_partido = (
            apuesta.get("estado") == "Pendiente"
            and texto_comparable(apuesta.get("equipo_local", "")) == texto_comparable(local)
            and texto_comparable(apuesta.get("equipo_visitante", "")) == texto_comparable(visitante)
        )
        if not mismo_partido:
            continue

        cantidad += 1
        usuario = estado.usuarios.get(apuesta.get("usuario"))
        if texto_comparable(apuesta.get("pronostico", "")) == texto_comparable(ganador):
            bruto = round(float(apuesta["monto"]) * float(apuesta["cuota"]), 2)
            neto = round(bruto - float(apuesta["monto"]), 2)
            apuesta.update({
                "estado": "Ganada",
                "ganancia_bruta": bruto,
                "ganancia_neta": neto,
            })
            if usuario:
                usuario.saldo += bruto
            logger.info("Apuesta ID %s ganada. Premio %.2f", apuesta["id"], bruto)
        else:
            apuesta.update({
                "estado": "Perdida",
                "ganancia_bruta": 0.0,
                "ganancia_neta": round(-float(apuesta["monto"]), 2),
            })
            logger.info("Apuesta ID %s perdida", apuesta["id"])

    return cantidad


def validar_apuestas_con_resultados(estado: EstadoSistema, partidos: list[dict]) -> int:
    total = 0
    for partido in partidos:
        if not partido.get("finalizado") or partido.get("conflicto"):
            continue
        gl = partido.get("goles_local")
        gv = partido.get("goles_visitante")
        if gl is None or gv is None:
            continue
        total += validar_apuestas_de_partido(
            estado,
            partido["equipo_local"],
            partido["equipo_visitante"],
            int(gl),
            int(gv),
        )
    if total:
        guardar_estado(estado)
    return total


def registrar_resultado_y_validar(estado: EstadoSistema) -> None:
    print("\n--- REGISTRAR RESULTADO Y VALIDAR APUESTAS ---")
    if not any(a.get("estado") == "Pendiente" for a in estado.apuestas):
        print("No existen apuestas pendientes.")
        return

    local = buscar_equipo(estado, input("Equipo local: "))
    visitante = buscar_equipo(estado, input("Equipo visitante: "))
    if local is None or visitante is None:
        print("Uno de los equipos no está registrado.")
        return
    if texto_comparable(local) == texto_comparable(visitante):
        print("Los equipos deben ser diferentes.")
        return

    goles_local = solicitar_entero(f"Goles de {local}: ", 0)
    goles_visitante = solicitar_entero(f"Goles de {visitante}: ", 0)
    ganador = _ganador(local, visitante, goles_local, goles_visitante)

    clave = clave_partido(local, visitante)
    estado.resultados[clave] = {
        "equipo_local": local,
        "equipo_visitante": visitante,
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "resultado": ganador,
        "estado": "Finalizado",
        "fuente": "Registro manual",
        "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    cantidad = validar_apuestas_de_partido(
        estado, local, visitante, goles_local, goles_visitante
    )
    guardar_estado(estado)
    print(f"\nResultado registrado: {local} {goles_local} - {goles_visitante} {visitante}")
    print(f"Apuestas validadas: {cantidad}")
    if cantidad == 0:
        print("No había apuestas pendientes para ese partido.")


def consultar_historial(estado: EstadoSistema) -> None:
    if not requiere_sesion(estado):
        return
    historial = [
        a for a in estado.apuestas
        if a.get("usuario") == estado.usuario_activo.correo
    ]
    print("\n--- HISTORIAL DE APUESTAS ---")
    if not historial:
        print("El usuario no tiene apuestas registradas.")
        return

    total_apostado = sum(float(a.get("monto", 0)) for a in historial)
    total_ganado = sum(float(a.get("ganancia_bruta", 0)) for a in historial)
    balance = sum(float(a.get("ganancia_neta", 0)) for a in historial)

    for apuesta in historial:
        print("\n----------------------------------------")
        print(f"ID: {apuesta['id']}")
        print(f"Fecha: {apuesta['fecha']}")
        print(f"Partido: {apuesta['equipo_local']} vs {apuesta['equipo_visitante']}")
        print(f"Pronóstico: {apuesta['pronostico']}")
        print(f"Monto: ${float(apuesta['monto']):.2f}")
        print(f"Cuota: {float(apuesta['cuota']):.2f}")
        print(f"Estado: {apuesta['estado']}")
        print(f"Ganancia neta: ${float(apuesta.get('ganancia_neta', 0)):.2f}")

    print("\n============== RESUMEN ==============")
    print(f"Total apostado: ${total_apostado:.2f}")
    print(f"Premios recibidos: ${total_ganado:.2f}")
    print(f"Balance neto: ${balance:.2f}")
    print(f"Saldo actual: ${estado.usuario_activo.saldo:.2f}")
