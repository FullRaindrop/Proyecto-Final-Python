from apuestas import consultar_historial, realizar_apuesta, registrar_resultado_y_validar
from pagos import depositar_fondos, retirar_fondos
from reportes import generar_reportes
from scraping import consultar_resultados_web
from usuarios import cerrar_sesion, iniciar_sesion, registrar_usuario
from utilidades import EstadoSistema, cargar_estado, guardar_estado, logger, pausar


def mostrar_menu(estado: EstadoSistema) -> None:
    sesion = (
        f"{estado.usuario_activo.nombre} | Saldo: ${estado.usuario_activo.saldo:.2f}"
        if estado.usuario_activo else "Ningún usuario conectado"
    )
    print("\n================================================")
    print("     SISTEMA DE APUESTAS MUNDIAL FIFA 2026")
    print("================================================")
    print(f"Sesión: {sesion}")
    print("------------------------------------------------")
    print("1. Registrar usuario")
    print("2. Iniciar sesión")
    print("3. Depositar fondos")
    print("4. Retirar fondos")
    print("5. Consultar resultados por Internet")
    print("6. Realizar apuesta")
    print("7. Registrar resultado manual y validar")
    print("8. Consultar historial de apuestas")
    print("9. Generar reportes Excel")
    print("10. Cerrar sesión")
    print("11. Salir")
    print("================================================")


def menu() -> None:
    estado = EstadoSistema()
    cargar_estado(estado)
    logger.info("Aplicación iniciada")

    acciones = {
        "1": registrar_usuario,
        "2": iniciar_sesion,
        "3": depositar_fondos,
        "4": retirar_fondos,
        "5": consultar_resultados_web,
        "6": realizar_apuesta,
        "7": registrar_resultado_y_validar,
        "8": consultar_historial,
        "9": generar_reportes,
        "10": cerrar_sesion,
    }

    while True:
        mostrar_menu(estado)
        opcion = input("Seleccione una opción: ").strip()
        if opcion == "11":
            guardar_estado(estado)
            logger.info("Aplicación cerrada")
            print("Saliendo del sistema...")
            break

        accion = acciones.get(opcion)
        if accion is None:
            print("Opción inválida.")
        else:
            accion(estado)
        pausar()


if __name__ == "__main__":
    menu()
