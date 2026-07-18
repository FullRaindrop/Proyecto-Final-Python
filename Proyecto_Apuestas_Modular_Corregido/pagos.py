from datetime import datetime

from usuarios import requiere_sesion
from utilidades import EstadoSistema, guardar_estado, logger, solicitar_float


METODOS_PAGO = {
    "1": "Tarjeta de Crédito",
    "2": "Tarjeta de Débito",
    "3": "PayPal",
    "4": "Yappy",
    "5": "Transferencia Bancaria",
}


def seleccionar_metodo_pago() -> str | None:
    print("\nMétodos de pago:")
    for numero, nombre in METODOS_PAGO.items():
        print(f"{numero}. {nombre}")
    return METODOS_PAGO.get(input("Seleccione una opción: ").strip())


def depositar_fondos(estado: EstadoSistema) -> None:
    if not requiere_sesion(estado):
        return

    print("\n--- DEPÓSITO DE FONDOS ---")
    metodo = seleccionar_metodo_pago()
    if metodo is None:
        print("Método de pago inválido.")
        return

    monto = solicitar_float("Monto a depositar: $", 0.01)
    estado.usuario_activo.saldo += monto
    estado.pagos.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": estado.usuario_activo.correo,
        "tipo": "Depósito",
        "metodo": metodo,
        "monto": round(monto, 2),
    })
    guardar_estado(estado)
    logger.info(
        "Depósito de %.2f mediante %s por %s",
        monto, metodo, estado.usuario_activo.correo,
    )
    print(f"Depósito realizado. Nuevo saldo: ${estado.usuario_activo.saldo:.2f}")


def retirar_fondos(estado: EstadoSistema) -> None:
    if not requiere_sesion(estado):
        return

    print("\n--- RETIRO DE FONDOS ---")
    metodo = seleccionar_metodo_pago()
    if metodo is None:
        print("Método de retiro inválido.")
        return

    monto = solicitar_float("Monto a retirar: $", 0.01)
    if monto > estado.usuario_activo.saldo:
        print("Saldo insuficiente para realizar el retiro.")
        return

    estado.usuario_activo.saldo -= monto
    estado.pagos.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": estado.usuario_activo.correo,
        "tipo": "Retiro",
        "metodo": metodo,
        "monto": round(monto, 2),
    })
    guardar_estado(estado)
    logger.info(
        "Retiro de %.2f mediante %s por %s",
        monto, metodo, estado.usuario_activo.correo,
    )
    print(f"Retiro realizado. Nuevo saldo: ${estado.usuario_activo.saldo:.2f}")
