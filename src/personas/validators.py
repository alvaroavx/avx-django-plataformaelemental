from django.core.exceptions import ValidationError


def limpiar_rut_chileno(value):
    return "".join(ch for ch in (value or "").upper() if ch.isalnum())


def rut_chileno_es_valido(value):
    rut_limpio = limpiar_rut_chileno(value)
    if not rut_limpio:
        return True
    if len(rut_limpio) < 2 or not rut_limpio[:-1].isdigit():
        return False

    cuerpo = rut_limpio[:-1]
    digito_verificador = rut_limpio[-1]
    acumulado = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        acumulado += int(digito) * multiplicador
        multiplicador += 1
        if multiplicador > 7:
            multiplicador = 2
    resto = 11 - (acumulado % 11)
    if resto == 11:
        esperado = "0"
    elif resto == 10:
        esperado = "K"
    else:
        esperado = str(resto)
    return digito_verificador == esperado


def formatear_rut_chileno(value):
    rut_limpio = limpiar_rut_chileno(value)
    if not rut_limpio:
        return ""
    cuerpo = rut_limpio[:-1]
    digito_verificador = rut_limpio[-1]
    cuerpo_formateado = f"{int(cuerpo):,}".replace(",", ".") if cuerpo.isdigit() else cuerpo
    return f"{cuerpo_formateado}-{digito_verificador}"


def validar_rut_chileno(value):
    if not value:
        return
    if not rut_chileno_es_valido(value):
        raise ValidationError("Ingresa un RUT chileno valido.", code="rut_invalido")
