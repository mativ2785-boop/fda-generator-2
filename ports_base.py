"""
ports/base.py
Clase base para configuración de puertos.
Cada puerto hereda de PortConfig e implementa sus reglas específicas.
"""


class PortConfig:
    """
    Clase base para configuración de un puerto.
    Define la interfaz que todos los puertos deben implementar.
    """

    # Nombre del puerto para mostrar en vouchers y sumario
    name        = "Port"
    # Nombre corto para el voucher (sin "Port")
    short_name  = "PORT"

    # Orden canónico de vouchers para este puerto
    VOUCHER_ORDER = []

    # Keywords para detectar proveedores por contenido del PDF
    # Formato: { "categoria": [["kw1","kw2"], ["kw_alt"]] }
    # Cada sublista es un grupo AND; grupos entre sí son OR
    PROVIDER_SIGNATURES = {}

    def classify_provider(self, text, fname=""):
        """
        Clasifica un PDF por su contenido/nombre usando las firmas del puerto.
        Retorna la categoría o None.
        """
        fname_upper = fname.upper()
        for category, sig_groups in self.PROVIDER_SIGNATURES.items():
            for group in sig_groups:
                if all(kw in text or kw in fname_upper for kw in group):
                    return category
        return None

    def build_invoice_map(self, analysis, work_dir, line_amounts):
        """
        Construye el invoice_map para este puerto.
        Debe ser implementado por cada subclase.
        """
        raise NotImplementedError

    def get_maritime_voucher(self, category):
        """
        Dado el category de una página Maritime, retorna el voucher destino.
        Puede ser sobreescrito por cada puerto si tiene reglas distintas.
        """
        return MARITIME_PAGE_TO_VOUCHER.get(category)


# Mapa universal de categorías Maritime → voucher (compartido por todos los puertos)
MARITIME_PAGE_TO_VOUCHER = {
    "headclerk_break":   "HEADCLERK COMPULSORY SERVICES",
    "headclerk_liq":     "HEADCLERK COMPULSORY SERVICES",
    "watchmen_break":    "WATCHMEN COMPULSORY SERVICES",
    "watchmen_liq":      "WATCHMEN COMPULSORY SERVICES",
    "afip_lman":         "CUSTOM HOUSE EXPENSES",
    "se_inward":         "CUSTOM HOUSE EXPENSES",
    "se_permanencia":    "CUSTOM HOUSE PERMANENCE",
    "se_rancho":         "CUSTOM HOUSE (BUNKERING)",
    "migraciones_liq":   "MIGRATION EXPENSES",
    "migraciones_sol":   "MIGRATION EXPENSES",
    "orden_transporte":  "MIGRATION EXPENSES",
    "sanidad_cert":      "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_transf":    "SANITARY DUES AND FREE PRATIQUE",
    "sanidad_recibo":    "SANITARY DUES AND FREE PRATIQUE",
    "senasa":            "GARBAGE COMPULSORY INSPECTION",
    "amarradores_pag":   "MOORING & UNMOORING SERVICES",
    "mooring_img":       None,   # imágenes de scan → omitir
    "osro":              "OSRO ANNEX 18",
    "pest_pag":          "PEST CONTROL",
    "skip":              None,
    "skip_dup":          None,
    "unknown":           None,
}
