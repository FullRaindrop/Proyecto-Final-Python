import json
import logging
import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CARPETA_DATOS = BASE_DIR / "datos"
CARPETA_LOGS = BASE_DIR / "logs"

CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
CARPETA_LOGS.mkdir(parents=True, exist_ok=True)

ARCHIVO_USUARIOS = CARPETA_DATOS / "usuarios.json"
ARCHIVO_APUESTAS = CARPETA_DATOS / "apuestas.json"
ARCHIVO_PAGOS = CARPETA_DATOS / "pagos.json"
ARCHIVO_RESULTADOS = CARPETA_DATOS / "resultados.json"
ARCHIVO_CACHE_RESULTADOS = CARPETA_DATOS / "resultados_cache.json"

logger = logging.getLogger("sistema_apuestas")
logger.setLevel(logging.INFO)
if not logger.handlers:
    manejador = logging.FileHandler(
        CARPETA_LOGS / "auditoria.log", encoding="utf-8"
    )
    manejador.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(manejador)


ALIAS_EQUIPOS = {
    "argentina": "Argentina",
    "brazil": "Brasil",
    "brasil": "Brasil",
    "canada": "Canadá",
    "colombia": "Colombia",
    "ecuador": "Ecuador",
    "england": "Inglaterra",
    "inglaterra": "Inglaterra",
    "france": "Francia",
    "francia": "Francia",
    "germany": "Alemania",
    "alemania": "Alemania",
    "italy": "Italia",
    "italia": "Italia",
    "japan": "Japón",
    "japon": "Japón",
    "mexico": "México",
    "morocco": "Marruecos",
    "marruecos": "Marruecos",
    "netherlands": "Países Bajos",
    "paises bajos": "Países Bajos",
    "panama": "Panamá",
    "portugal": "Portugal",
    "senegal": "Senegal",
    "south korea": "Corea del Sur",
    "korea republic": "Corea del Sur",
    "corea del sur": "Corea del Sur",
    "spain": "España",
    "espana": "España",
    "united states": "Estados Unidos",
    "usa": "Estados Unidos",
    "estados unidos": "Estados Unidos",
    "uruguay": "Uruguay",
}

EQUIPOS_INICIALES = {
    "Alemania", "Argentina", "Brasil", "Canadá", "Colombia",
    "Corea del Sur", "Ecuador", "España", "Estados Unidos", "Francia",
    "Inglaterra", "Italia", "Japón", "Marruecos", "México", "Panamá",
    "Países Bajos", "Portugal", "Senegal", "Uruguay"
}


@dataclass
class EstadoSistema:
    usuarios: dict[str, Any] = field(default_factory=dict)
    apuestas: list[dict[str, Any]] = field(default_factory=list)
    pagos: list[dict[str, Any]] = field(default_factory=list)
    resultados: dict[str, dict[str, Any]] = field(default_factory=dict)
    usuario_activo: Any = None
    equipos: set[str] = field(default_factory=lambda: set(EQUIPOS_INICIALES))


def limpiar_pantalla() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pausar() -> None:
    input("\nPresione Enter para continuar...")


def guardar_json(ruta: Path, datos: Any) -> bool:
    """Guarda JSON de forma atómica para reducir archivos corruptos."""
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    try:
        with temporal.open("w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, indent=4, ensure_ascii=False)
        temporal.replace(ruta)
        return True
    except OSError as error:
        logger.error("Error al guardar %s: %s", ruta, error)
        print(f"No se pudo guardar el archivo {ruta.name}.")
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def cargar_json(ruta: Path, predeterminado: Any) -> Any:
    try:
        if not ruta.exists():
            return predeterminado
        with ruta.open("r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, json.JSONDecodeError) as error:
        logger.error("Error al cargar %s: %s", ruta, error)
        return predeterminado


def cargar_estado(estado: EstadoSistema) -> None:
    # Importación local para evitar dependencia circular.
    from usuarios import Usuario

    datos_usuarios = cargar_json(ARCHIVO_USUARIOS, {})
    estado.usuarios = {
        correo: Usuario.from_dict(datos)
        for correo, datos in datos_usuarios.items()
    }
    estado.apuestas = cargar_json(ARCHIVO_APUESTAS, [])
    estado.pagos = cargar_json(ARCHIVO_PAGOS, [])
    estado.resultados = cargar_json(ARCHIVO_RESULTADOS, {})

    # Los equipos obtenidos por Internet también pasan a formar parte del conjunto.
    for resultado in estado.resultados.values():
        local = resultado.get("equipo_local")
        visitante = resultado.get("equipo_visitante")
        if local:
            estado.equipos.add(local)
        if visitante:
            estado.equipos.add(visitante)


def guardar_estado(estado: EstadoSistema) -> None:
    usuarios_serializados = {
        correo: usuario.to_dict()
        for correo, usuario in estado.usuarios.items()
    }
    guardar_json(ARCHIVO_USUARIOS, usuarios_serializados)
    guardar_json(ARCHIVO_APUESTAS, estado.apuestas)
    guardar_json(ARCHIVO_PAGOS, estado.pagos)
    guardar_json(ARCHIVO_RESULTADOS, estado.resultados)


def solicitar_float(mensaje: str, minimo: float | None = None) -> float:
    while True:
        try:
            texto = input(mensaje).strip().replace(",", ".")
            valor = float(texto)
            if minimo is not None and valor < minimo:
                print(f"El valor debe ser mayor o igual a {minimo}.")
                continue
            return valor
        except ValueError:
            print("Ingrese un número válido.")


def solicitar_entero(mensaje: str, minimo: int | None = None) -> int:
    while True:
        try:
            valor = int(input(mensaje).strip())
            if minimo is not None and valor < minimo:
                print(f"El valor debe ser mayor o igual a {minimo}.")
                continue
            return valor
        except ValueError:
            print("Ingrese un número entero válido.")


def texto_comparable(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.strip().casefold())
    sin_tildes = "".join(c for c in normalizado if not unicodedata.combining(c))
    return " ".join(sin_tildes.split())


def nombre_equipo(nombre: str) -> str:
    limpio = " ".join(nombre.strip().split())
    canonico = ALIAS_EQUIPOS.get(texto_comparable(limpio))
    return canonico if canonico else limpio.title()


def buscar_equipo(estado: EstadoSistema, nombre: str) -> str | None:
    buscado = texto_comparable(nombre)
    canonico = ALIAS_EQUIPOS.get(buscado)
    if canonico:
        buscado = texto_comparable(canonico)
    for equipo in estado.equipos:
        if texto_comparable(equipo) == buscado:
            return equipo
    return None


def registrar_equipo(estado: EstadoSistema, nombre: str) -> str:
    existente = buscar_equipo(estado, nombre)
    if existente:
        return existente
    limpio = nombre_equipo(nombre)
    estado.equipos.add(limpio)
    return limpio


def clave_partido(local: str, visitante: str, fecha_iso: str = "") -> str:
    base = f"{texto_comparable(local)}|{texto_comparable(visitante)}"
    return f"{fecha_iso}|{base}" if fecha_iso else base
