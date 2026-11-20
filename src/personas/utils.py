import re


def normalizar_telefono(telefono):
    """Normaliza telefonos para uso operacional, priorizando numeros chilenos."""
    valor = (telefono or "").strip()
    if not valor:
        return ""

    valor = re.sub(r"[\s\-\(\)]", "", valor)
    valor = valor.replace("＋", "+")

    if valor.startswith("00"):
        valor = f"+{valor[2:]}"

    if valor.startswith("+"):
        digitos_internacionales = re.sub(r"\D", "", valor[1:])
        return f"+{digitos_internacionales}"

    digitos = re.sub(r"\D", "", valor)
    if digitos.startswith("56"):
        return f"+{digitos}"
    if len(digitos) == 9 and digitos.startswith("9"):
        return f"+56{digitos}"
    return digitos


def tiene_identidad_minima(*, rut="", email="", telefono=""):
    return any(
        [
            (rut or "").strip(),
            (email or "").strip(),
            normalizar_telefono(telefono),
        ]
    )
