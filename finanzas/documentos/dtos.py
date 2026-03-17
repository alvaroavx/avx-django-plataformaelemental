from dataclasses import dataclass, field
from decimal import Decimal


def _serialize_value(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


@dataclass
class NormalizedField:
    value: object = None
    source: str = "inferred"
    confidence: str = "low"

    def to_dict(self):
        return {
            "value": _serialize_value(self.value),
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload):
        if payload is None:
            return cls()
        value = payload.get("value")
        return cls(value=value, source=payload.get("source", "inferred"), confidence=payload.get("confidence", "low"))


@dataclass
class NormalizedTaxLine:
    fields: dict[str, NormalizedField] = field(default_factory=dict)

    def set_field(self, key, value, source="inferred", confidence="low"):
        self.fields[key] = NormalizedField(value=value, source=source, confidence=confidence)

    def to_dict(self):
        return {key: field.to_dict() for key, field in self.fields.items()}

    @classmethod
    def from_dict(cls, payload):
        return cls(fields={key: NormalizedField.from_dict(value) for key, value in (payload or {}).items()})


@dataclass
class NormalizedTaxDocument:
    encabezado: dict[str, NormalizedField] = field(default_factory=dict)
    emisor: dict[str, NormalizedField] = field(default_factory=dict)
    receptor: dict[str, NormalizedField] = field(default_factory=dict)
    montos: dict[str, NormalizedField] = field(default_factory=dict)
    metadata_archivo: dict[str, NormalizedField] = field(default_factory=dict)
    lineas: list[NormalizedTaxLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    posibles_duplicados: list[dict] = field(default_factory=list)
    sugerencias_mapeo: dict[str, object] = field(default_factory=dict)

    def set_field(self, section, key, value, source="inferred", confidence="low"):
        getattr(self, section)[key] = NormalizedField(value=value, source=source, confidence=confidence)

    def get_value(self, section, key, default=None):
        field = getattr(self, section).get(key)
        return field.value if field else default

    def to_dict(self):
        return {
            "encabezado": {key: value.to_dict() for key, value in self.encabezado.items()},
            "emisor": {key: value.to_dict() for key, value in self.emisor.items()},
            "receptor": {key: value.to_dict() for key, value in self.receptor.items()},
            "montos": {key: value.to_dict() for key, value in self.montos.items()},
            "metadata_archivo": {key: value.to_dict() for key, value in self.metadata_archivo.items()},
            "lineas": [linea.to_dict() for linea in self.lineas],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "posibles_duplicados": list(self.posibles_duplicados),
            "sugerencias_mapeo": self.sugerencias_mapeo,
        }

    @classmethod
    def from_dict(cls, payload):
        documento = cls(
            warnings=list((payload or {}).get("warnings", [])),
            errors=list((payload or {}).get("errors", [])),
            posibles_duplicados=list((payload or {}).get("posibles_duplicados", [])),
            sugerencias_mapeo=dict((payload or {}).get("sugerencias_mapeo", {})),
        )
        for section in ("encabezado", "emisor", "receptor", "montos", "metadata_archivo"):
            setattr(
                documento,
                section,
                {
                    key: NormalizedField.from_dict(value)
                    for key, value in ((payload or {}).get(section, {}) or {}).items()
                },
            )
        documento.lineas = [NormalizedTaxLine.from_dict(item) for item in (payload or {}).get("lineas", [])]
        return documento
