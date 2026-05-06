"""
ports/__init__.py
Registro de puertos disponibles en el FDA Generator.
Para agregar un puerto nuevo:
  1. Crear ports/nombre_puerto.py con la clase PortConfig
  2. Registrarlo en PORT_REGISTRY abajo
"""

from .bahia_blanca import BahiaBlancaPort
from .necochea     import NecocheaPort

# Registro: clave = nombre interno, valor = clase de configuración
PORT_REGISTRY = {
    "bahia_blanca": BahiaBlancaPort,
    "necochea":     NecocheaPort,
}


def detect_port(analysis):
    """
    Detecta el puerto a partir del análisis de los PDFs.
    Usa el nombre del puerto extraído de las FACBs o SOF.
    Retorna una instancia del PortConfig correspondiente.
    """
    port_str = (analysis.get("port") or "").upper()

    if "NECOCHEA" in port_str or "QUEQUEN" in port_str or "QUEQUÉN" in port_str:
        return NecocheaPort()
    if "BAHIA BLANCA" in port_str or "BAHÍA BLANCA" in port_str:
        return BahiaBlancaPort()

    # Fallback: intentar detectar por proveedores encontrados
    all_files = " ".join(
        analysis.get("consorcio", []) +
        analysis.get("donmar", []) +
        analysis.get("puerto_mariel", []) +
        analysis.get("pilotaje", []) +
        analysis.get("mooring", [])
    ).upper()

    if "QUEQUEN" in all_files or "MELLUSO" in all_files or "MEYER" in all_files:
        return NecocheaPort()

    # Default: Bahia Blanca
    return BahiaBlancaPort()


def get_port(port_key):
    """Retorna instancia de un puerto por su clave."""
    cls = PORT_REGISTRY.get(port_key)
    if not cls:
        raise ValueError(f"Puerto desconocido: {port_key}. "
                         f"Disponibles: {list(PORT_REGISTRY.keys())}")
    return cls()
