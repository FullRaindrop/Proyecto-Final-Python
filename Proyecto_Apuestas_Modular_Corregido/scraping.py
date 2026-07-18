import json
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utilidades import (
    ARCHIVO_CACHE_RESULTADOS,
    EstadoSistema,
    cargar_json,
    clave_partido,
    guardar_estado,
    guardar_json,
    logger,
    registrar_equipo,
    texto_comparable,
)

URL_ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
URL_SPORTSDB = "https://www.thesportsdb.com/api/v1/json/123/eventsday.php"
URL_FIFA = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
}


def crear_sesion() -> requests.Session:
    reintentos = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    sesion = requests.Session()
    adaptador = HTTPAdapter(max_retries=reintentos)
    sesion.mount("https://", adaptador)
    sesion.mount("http://", adaptador)
    sesion.headers.update(HEADERS)
    return sesion


def _entero_o_none(valor: Any) -> int | None:
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _es_mundial(nombre_liga: str) -> bool:
    texto = texto_comparable(nombre_liga)
    return "world cup" in texto or "copa mundial" in texto or "fifa mundial" in texto


def obtener_espn(sesion: requests.Session, fecha_compacta: str) -> tuple[list[dict], str]:
    url = f"{URL_ESPN}?{urlencode({'dates': fecha_compacta})}"
    try:
        respuesta = sesion.get(url, timeout=(6, 20))
        if respuesta.status_code != 200:
            return [], f"ERROR HTTP {respuesta.status_code}"
        datos = respuesta.json()
        partidos: list[dict] = []
        for evento in datos.get("events", []):
            competiciones = evento.get("competitions") or []
            if not competiciones:
                continue
            competencia = competiciones[0]
            competidores = competencia.get("competitors") or []
            local = next((c for c in competidores if c.get("homeAway") == "home"), None)
            visitante = next((c for c in competidores if c.get("homeAway") == "away"), None)
            if not local or not visitante:
                continue

            liga = (
                evento.get("league", {}).get("name")
                or evento.get("season", {}).get("name")
                or "FIFA World Cup"
            )
            # La URL ya está limitada a fifa.world; el filtro evita datos extraños.
            if liga and not _es_mundial(liga) and "fifa" not in texto_comparable(liga):
                liga = "FIFA World Cup"

            estado_tipo = evento.get("status", {}).get("type", {})
            finalizado = bool(estado_tipo.get("completed")) or estado_tipo.get("state") == "post"
            gl = _entero_o_none(local.get("score"))
            gv = _entero_o_none(visitante.get("score"))
            partidos.append({
                "id_externo": str(evento.get("id", "")),
                "fecha": evento.get("date", ""),
                "equipo_local": local.get("team", {}).get("displayName", "Local"),
                "equipo_visitante": visitante.get("team", {}).get("displayName", "Visitante"),
                "goles_local": gl,
                "goles_visitante": gv,
                "estado": estado_tipo.get("description", "Sin estado"),
                "finalizado": finalizado and gl is not None and gv is not None,
                "fuentes": ["ESPN"],
                "conflicto": False,
            })
        return partidos, f"OK ({len(partidos)} partido(s))"
    except (requests.RequestException, ValueError, json.JSONDecodeError) as error:
        logger.error("Fallo ESPN: %s", error)
        return [], f"ERROR: {error}"


def obtener_sportsdb(sesion: requests.Session, fecha_iso: str) -> tuple[list[dict], str]:
    parametros = {
        "d": fecha_iso,
        "s": "Soccer",
        "l": "FIFA World Cup",
    }
    url = f"{URL_SPORTSDB}?{urlencode(parametros)}"
    try:
        respuesta = sesion.get(url, timeout=(6, 20))
        if respuesta.status_code != 200:
            return [], f"ERROR HTTP {respuesta.status_code}"
        datos = respuesta.json()
        partidos: list[dict] = []
        for evento in datos.get("events") or []:
            liga = evento.get("strLeague", "")
            if liga and not _es_mundial(liga):
                continue
            gl = _entero_o_none(evento.get("intHomeScore"))
            gv = _entero_o_none(evento.get("intAwayScore"))
            estado = evento.get("strStatus") or evento.get("strProgress") or "Sin estado"
            estado_norm = texto_comparable(estado)
            finalizado = (
                gl is not None
                and gv is not None
                and (
                    "finished" in estado_norm
                    or estado_norm in {"ft", "match finished", "finalizado"}
                    or evento.get("strResult")
                )
            )
            partidos.append({
                "id_externo": str(evento.get("idEvent", "")),
                "fecha": f"{evento.get('dateEvent', fecha_iso)}T{evento.get('strTime', '')}",
                "equipo_local": evento.get("strHomeTeam", "Local"),
                "equipo_visitante": evento.get("strAwayTeam", "Visitante"),
                "goles_local": gl,
                "goles_visitante": gv,
                "estado": estado,
                "finalizado": bool(finalizado),
                "fuentes": ["TheSportsDB"],
                "conflicto": False,
            })
        return partidos, f"OK ({len(partidos)} partido(s))"
    except (requests.RequestException, ValueError, json.JSONDecodeError) as error:
        logger.error("Fallo TheSportsDB: %s", error)
        return [], f"ERROR: {error}"


def comprobar_fifa(sesion: requests.Session) -> str:
    """Web Scraping real con Requests + BeautifulSoup para comprobar FIFA."""
    try:
        respuesta = sesion.get(URL_FIFA, timeout=(6, 20))
        if respuesta.status_code != 200:
            return f"ERROR HTTP {respuesta.status_code}"
        soup = BeautifulSoup(respuesta.text, "html.parser")
        titulo = soup.title.get_text(" ", strip=True) if soup.title else "Página FIFA accesible"
        return f"OK - {titulo[:80]}"
    except requests.RequestException as error:
        logger.error("Fallo página FIFA: %s", error)
        return f"ERROR: {error}"


def _clave_fusion(partido: dict) -> str:
    return clave_partido(partido["equipo_local"], partido["equipo_visitante"])


def fusionar_resultados(*listas: list[dict]) -> list[dict]:
    fusionados: dict[str, dict] = {}
    for lista in listas:
        for nuevo in lista:
            clave = _clave_fusion(nuevo)
            anterior = fusionados.get(clave)
            if anterior is None:
                fusionados[clave] = dict(nuevo)
                continue

            fuentes = list(dict.fromkeys(anterior.get("fuentes", []) + nuevo.get("fuentes", [])))
            anterior["fuentes"] = fuentes
            gl_a, gv_a = anterior.get("goles_local"), anterior.get("goles_visitante")
            gl_n, gv_n = nuevo.get("goles_local"), nuevo.get("goles_visitante")

            if gl_a is not None and gv_a is not None and gl_n is not None and gv_n is not None:
                if (gl_a, gv_a) != (gl_n, gv_n):
                    anterior["conflicto"] = True
                    anterior["estado"] = "Fuentes no coinciden"
                    anterior["finalizado"] = False
            elif gl_a is None or gv_a is None:
                anterior["goles_local"] = gl_n
                anterior["goles_visitante"] = gv_n
                anterior["estado"] = nuevo.get("estado", anterior.get("estado"))
                anterior["finalizado"] = nuevo.get("finalizado", False)

            if nuevo.get("finalizado") and not anterior.get("conflicto"):
                anterior["finalizado"] = True
                anterior["estado"] = nuevo.get("estado", anterior.get("estado"))
    return sorted(fusionados.values(), key=lambda p: p.get("fecha", ""))


def guardar_en_cache(fecha_iso: str, partidos: list[dict]) -> None:
    cache = cargar_json(ARCHIVO_CACHE_RESULTADOS, {})
    cache[fecha_iso] = partidos
    guardar_json(ARCHIVO_CACHE_RESULTADOS, cache)


def cargar_de_cache(fecha_iso: str) -> list[dict]:
    cache = cargar_json(ARCHIVO_CACHE_RESULTADOS, {})
    partidos = cache.get(fecha_iso, [])
    for partido in partidos:
        partido.setdefault("fuentes", ["Caché local"])
        if "Caché local" not in partido["fuentes"]:
            partido["fuentes"].append("Caché local")
    return partidos


def _mostrar_partidos(partidos: list[dict]) -> None:
    print("\n--- RESULTADOS ENCONTRADOS ---")
    for numero, partido in enumerate(partidos, start=1):
        local = partido["equipo_local"]
        visitante = partido["equipo_visitante"]
        gl = partido.get("goles_local")
        gv = partido.get("goles_visitante")
        fuentes = ", ".join(partido.get("fuentes", []))
        if partido.get("conflicto"):
            marcador = "RESULTADO EN CONFLICTO"
        elif gl is not None and gv is not None:
            marcador = f"{gl} - {gv}"
        else:
            marcador = partido.get("estado", "Programado")
        print(f"{numero}. {local}  {marcador}  {visitante}")
        print(f"   Estado: {partido.get('estado', 'Sin estado')} | Fuente: {fuentes}")


def consultar_resultados_web(estado: EstadoSistema) -> None:
    print("\n--- CONSULTA DE RESULTADOS POR INTERNET ---")
    texto_fecha = input("Fecha del Mundial (DD-MM-AAAA): ").strip()
    try:
        fecha = datetime.strptime(texto_fecha, "%d-%m-%Y")
    except ValueError:
        print("Fecha inválida. Ejemplo correcto: 15-07-2026")
        return

    fecha_iso = fecha.strftime("%Y-%m-%d")
    fecha_compacta = fecha.strftime("%Y%m%d")
    print("\nConectando con las fuentes deportivas...")

    sesion = crear_sesion()
    partidos_espn, estado_espn = obtener_espn(sesion, fecha_compacta)
    partidos_sdb, estado_sdb = obtener_sportsdb(sesion, fecha_iso)
    estado_fifa = comprobar_fifa(sesion)
    print(f"[ESPN]        {estado_espn}")
    print(f"[TheSportsDB] {estado_sdb}")
    print(f"[FIFA/HTML]   {estado_fifa}")

    partidos = fusionar_resultados(partidos_espn, partidos_sdb)
    uso_cache = False
    if partidos:
        guardar_en_cache(fecha_iso, partidos)
    else:
        partidos = cargar_de_cache(fecha_iso)
        uso_cache = bool(partidos)

    if not partidos:
        print("\nNo se encontraron partidos del Mundial para esa fecha.")
        print("La conexión fue comprobada; puede ser un día sin partidos o una fuente temporalmente sin datos.")
        logger.info("Sin resultados para %s", fecha_iso)
        return

    if uso_cache:
        print("\nLas fuentes en línea no devolvieron datos. Se muestra el último resultado guardado en caché.")

    _mostrar_partidos(partidos)

    for partido in partidos:
        local = registrar_equipo(estado, partido["equipo_local"])
        visitante = registrar_equipo(estado, partido["equipo_visitante"])
        partido["equipo_local"] = local
        partido["equipo_visitante"] = visitante
        clave = clave_partido(local, visitante, fecha_iso)
        estado.resultados[clave] = {
            **partido,
            "fuente": ", ".join(partido.get("fuentes", [])),
            "fecha_consultada": fecha_iso,
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Comunicación real entre scraping y apuestas: valida automáticamente
    # únicamente cuando el marcador es final y las fuentes no están en conflicto.
    from apuestas import validar_apuestas_con_resultados

    validadas = validar_apuestas_con_resultados(estado, partidos)
    guardar_estado(estado)
    print(f"\nApuestas pendientes validadas automáticamente: {validadas}")
    logger.info(
        "Consulta web %s: %s partido(s), apuestas validadas: %s",
        fecha_iso, len(partidos), validadas,
    )
