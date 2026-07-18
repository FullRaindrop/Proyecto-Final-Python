from utilidades import EstadoSistema, guardar_estado, logger, solicitar_entero


class Usuario:
    def __init__(
        self,
        nombre: str,
        apellido: str,
        correo: str,
        edad: int,
        password: str,
        saldo: float = 0.0,
    ) -> None:
        self.nombre = nombre
        self.apellido = apellido
        self.correo = correo
        self.edad = edad
        self.password = password
        self.saldo = float(saldo)

    def to_dict(self) -> dict:
        return {
            "nombre": self.nombre,
            "apellido": self.apellido,
            "correo": self.correo,
            "edad": self.edad,
            "password": self.password,
            "saldo": round(self.saldo, 2),
        }

    @staticmethod
    def from_dict(datos: dict) -> "Usuario":
        return Usuario(
            datos["nombre"],
            datos["apellido"],
            datos["correo"],
            int(datos["edad"]),
            datos["password"],
            float(datos.get("saldo", 0.0)),
        )


def registrar_usuario(estado: EstadoSistema) -> None:
    print("\n--- REGISTRO DE USUARIO ---")
    try:
        nombre = input("Nombre: ").strip()
        apellido = input("Apellido: ").strip()
        correo = input("Correo electrónico: ").strip().lower()
        edad = solicitar_entero("Edad: ", 18)
        password = input("Contraseña: ").strip()

        if not all((nombre, apellido, correo, password)):
            print("Todos los campos son obligatorios.")
            return
        if "@" not in correo or "." not in correo.rsplit("@", 1)[-1]:
            print("El correo electrónico no parece válido.")
            return
        if correo in estado.usuarios:
            print("Ya existe un usuario registrado con ese correo.")
            return

        estado.usuarios[correo] = Usuario(
            nombre, apellido, correo, edad, password
        )
        guardar_estado(estado)
        logger.info("Usuario registrado: %s", correo)
        print("Usuario registrado exitosamente.")
    except Exception as error:
        logger.exception("Error inesperado al registrar usuario: %s", error)
        print("Ocurrió un error inesperado durante el registro.")


def iniciar_sesion(estado: EstadoSistema) -> None:
    print("\n--- INICIAR SESIÓN ---")
    correo = input("Correo electrónico: ").strip().lower()
    password = input("Contraseña: ").strip()
    usuario = estado.usuarios.get(correo)

    if usuario and usuario.password == password:
        estado.usuario_activo = usuario
        logger.info("Inicio de sesión: %s", correo)
        print(f"Bienvenido, {usuario.nombre} {usuario.apellido}.")
        print(f"Saldo disponible: ${usuario.saldo:.2f}")
    else:
        logger.warning("Intento fallido de inicio de sesión: %s", correo)
        print("Credenciales incorrectas.")


def cerrar_sesion(estado: EstadoSistema) -> None:
    if estado.usuario_activo is None:
        print("No hay una sesión activa.")
        return
    correo = estado.usuario_activo.correo
    estado.usuario_activo = None
    logger.info("Cierre de sesión: %s", correo)
    print("Sesión cerrada correctamente.")


def requiere_sesion(estado: EstadoSistema) -> bool:
    if estado.usuario_activo is None:
        print("Debe iniciar sesión primero.")
        return False
    return True
