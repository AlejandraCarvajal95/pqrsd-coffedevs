"""Paso 3: anonimiza los textos y reemplaza los datos personales por datos ficticios.

Regla del proyecto (CLAUDE.md): solo datos ficticios, nada de datos personales reales.
Los textos de datos.gov.co son públicos, pero traen nombres, cédulas, teléfonos y
matrículas de personas reales. Aquí se reemplazan por valores ficticios coherentes
(Faker es_CO), no por etiquetas, para que el texto siga pareciendo una PQRS real.

- Español: spaCy (es_core_news_md) para nombres + expresiones regulares.
- Inglés (CFPB ya viene censurado con XXXX; BANKING77 no trae datos): solo regex.
El reetiquetado (paso 4) revisa además si quedó algún dato personal y descarta esas filas.
"""

import random
import re
import sys
import zlib

import pandas as pd
import spacy
from faker import Faker

sys.path.insert(0, "/data/scripts/dataset")
from config import INTERMEDIO  # noqa: E402

NO_SON_NOMBRES = {
    "buenas", "buenos", "buen", "cordial", "cordialmente", "señores", "señor", "señora", "alcaldía",
    "alcaldia", "ministerio", "secretaría", "secretaria", "gobernación", "contraloría", "municipio",
    "doctor", "doctora", "respetados", "apreciados", "estimados", "atentamente", "gracias", "liga",
    "club", "federación", "derecho", "petición", "colombia", "bogotá", "flandes", "banco", "notaría",
}

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
RE_URL = re.compile(r"(https?://|www\.)\S+", re.I)
RE_DOC = re.compile(
    r"(?i)\b(c\.?\s?c\.?|c[ée]dula(?:\s+de\s+ciudadan[ií]a)?|nit|t\.?\s?i\.?|identificad[oa]\s+con"
    r"(?:\s+(?:la\s+)?c[ée]dula(?:\s+de\s+ciudadan[ií]a)?)?|documento(?:\s+de\s+identidad)?)"
    r"(\s*(?:n[°oº.]*|no\.?|número|:)?\s*)(\d[\d.\s]{4,14}\d)"
)
RE_CEL = re.compile(r"(?<!\d)(\+?57[\s-]?)?3\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
RE_FIJO = re.compile(r"(?<!\d)60\d[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
RE_DIR = re.compile(
    r"(?i)\b(calle|carrera|cra\.?|kra\.?|cr\.?|cll\.?|cl\.?|avenida|av\.?|transversal|tv\.?|diagonal|dg\.?)"
    r"\s*\d+\s*[a-z]?\s*(bis)?\s*(#|n[°oº.]*|no\.?)\s*\d+\s*[a-z]?\s*-\s*\d+"
)
RE_SERIE = re.compile(r"\b\d{2,}(?:[-.]\d{2,}){2,}\b")  # matrículas, cédulas catastrales
RE_LARGO = re.compile(r"(?<!\d)\d{6,}(?!\d)")  # radicados, cuentas, cédulas (aunque estén pegados a letras)
RE_CONTEXTO_NOMBRE = re.compile(
    r"(?i:mi nombre es|me llamo|suscrit[oa]|yo,|señora|señor|sra\.?|sr\.?|doctora|doctor|dra\.?|dr\.?|"
    r"atentamente,?|cordialmente,?|firma:?)\s+"
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3}"
    r"|[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,}){1,3})"
)


def digitos_al_azar(texto: str, rnd: random.Random) -> str:
    return re.sub(r"\d", lambda _: str(rnd.randint(0, 9)), texto)


class Anonimizador:
    def __init__(self):
        self.nlp = spacy.load("es_core_news_md", disable=["parser", "lemmatizer", "attribute_ruler"])

    def nombres_spacy(self, textos: list[str]) -> list[list[tuple[int, int]]]:
        """Tramos de nombres de persona (2 a 4 palabras con mayúscula inicial)."""
        # En textos todo en mayúsculas el modelo no reconoce nombres: se le pasa en
        # formato título (misma longitud, así los índices siguen sirviendo).
        entrada = [t.title() if sum(c.isupper() for c in t) > 0.6 * max(1, sum(c.isalpha() for c in t)) else t
                   for t in textos]
        salida = []
        for doc in self.nlp.pipe(entrada, batch_size=64):
            tramos = []
            for ent in doc.ents:
                palabras = ent.text.split()
                if ent.label_ != "PER" or not 2 <= len(palabras) <= 4:
                    continue
                if any(p.lower().strip(".,") in NO_SON_NOMBRES for p in palabras):
                    continue
                if not all(p[0].isupper() for p in palabras if p.lower() not in ("de", "del", "la")):
                    continue
                tramos.append((ent.start_char, ent.end_char))
            salida.append(tramos)
        return salida

    def anonimizar(self, texto: str, id_fila: str, tramos_nombre=()) -> tuple[str, int]:
        semilla = zlib.crc32(id_fila.encode())
        rnd, fake = random.Random(semilla), Faker("es_CO")
        fake.seed_instance(semilla)
        n = 0
        nombres: dict[str, str] = {}

        def nombre_ficticio(real: str) -> str:
            clave = real.lower()
            if clave not in nombres:
                ficticio = f"{fake.first_name()} {fake.last_name()}"
                nombres[clave] = ficticio.upper() if real.isupper() else ficticio
            return nombres[clave]

        # Nombres de spaCy (de atrás hacia adelante para no mover los índices).
        for ini, fin in sorted(tramos_nombre, reverse=True):
            texto = texto[:ini] + nombre_ficticio(texto[ini:fin]) + texto[fin:]
            n += 1

        def sub(patron, reemplazo):
            nonlocal texto, n
            texto, k = patron.subn(reemplazo, texto)
            n += k

        sub(RE_EMAIL, lambda m: fake.free_email())
        sub(RE_URL, lambda m: "https://www.ejemplo.com.co")
        sub(RE_DOC, lambda m: m.group(1) + m.group(2) + digitos_al_azar(m.group(3), rnd))
        sub(RE_CEL, lambda m: f"3{rnd.randint(0, 2)}{rnd.randint(0, 9)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}")
        sub(RE_FIJO, lambda m: f"60{rnd.randint(1, 8)} {rnd.randint(100, 999)} {rnd.randint(1000, 9999)}")
        sub(RE_DIR, lambda m: fake.street_address())
        sub(RE_SERIE, lambda m: digitos_al_azar(m.group(0), rnd))
        sub(RE_LARGO, lambda m: digitos_al_azar(m.group(0), rnd))
        sub(RE_CONTEXTO_NOMBRE, lambda m: m.group(0)[: m.start(1) - m.start(0)] + nombre_ficticio(m.group(1)))
        return texto, n


if __name__ == "__main__":
    an = Anonimizador()
    for ruta in sorted(INTERMEDIO.glob("candidatos_*.parquet")):
        df = pd.read_parquet(ruta)
        es = (df["idioma"] == "es").to_numpy()
        tramos = [[] for _ in range(len(df))]
        if es.any():
            for i, t in zip(df.index[es], an.nombres_spacy(df.loc[es, "texto_original"].tolist())):
                tramos[df.index.get_loc(i)] = t
        res = [an.anonimizar(t, i, tr) for t, i, tr in zip(df["texto_original"], df["id"], tramos)]
        df["texto_anon"] = [r[0] for r in res]
        df["n_datos_reemplazados"] = [r[1] for r in res]
        destino = INTERMEDIO / ruta.name.replace("candidatos_", "anonimizado_")
        df.drop(columns=["texto_original"]).to_parquet(destino, index=False)
        print(f"{ruta.name}: {len(df)} filas, {int((df['n_datos_reemplazados'] > 0).sum())} con datos reemplazados")

    # Entrada del reetiquetado (paso 4): solo textos en español ya anonimizados.
    # CFPB y BANKING77 se reetiquetan en el mismo paso de la traducción.
    todos = pd.concat([pd.read_parquet(p) for p in INTERMEDIO.glob("anonimizado_*.parquet")])
    sel = todos[todos["grupo"].isin(["datos_gov", "amazon_sugerencia"])]
    sel[["id", "grupo", "tipo_mapeo", "texto_anon"]].rename(columns={"texto_anon": "texto"}).to_json(
        INTERMEDIO / "para_reetiquetar.jsonl", orient="records", lines=True, force_ascii=False
    )
    print(f"para_reetiquetar.jsonl: {len(sel)} textos")

    # Entrada de la traducción (06_traducir.py): CFPB y BANKING77.
    tra = todos[todos["fuente"].isin(["cfpb", "banking77"])]
    tra[["id", "fuente", "texto_anon"]].to_json(
        INTERMEDIO / "para_traducir.jsonl", orient="records", lines=True, force_ascii=False
    )
    print(f"para_traducir.jsonl: {len(tra)} textos")
