from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter(name="clp")
def clp(value):
    if value in (None, ""):
        return "$ 0"
    try:
        monto = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    monto = monto.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    signo = "-" if monto < 0 else ""
    entero = f"{abs(int(monto)):,}".replace(",", ".")
    return f"{signo}$ {entero}"
