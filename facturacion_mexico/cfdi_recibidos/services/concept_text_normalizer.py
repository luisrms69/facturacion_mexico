"""
Normalizador de texto para matching semántico en resolución de Items CFDI.
"""

import re
import unicodedata

_STOPWORDS = frozenset(
	[
		"de",
		"del",
		"la",
		"el",
		"los",
		"las",
		"un",
		"una",
		"unos",
		"unas",
		"y",
		"o",
		"a",
		"en",
		"con",
		"por",
		"para",
		"al",
		"se",
		"su",
		"sus",
		"que",
		"no",
		"es",
		"son",
		"ha",
		"han",
		"ser",
		"como",
	]
)

_ABBREVS: dict[str, str] = {
	"serv": "servicio",
	"svc": "servicio",
	"mto": "mantenimiento",
	"mant": "mantenimiento",
	"adm": "administracion",
	"admin": "administracion",
	"mat": "material",
	"inst": "instalacion",
	"rep": "reparacion",
	"tec": "tecnico",
	"comb": "combustible",
	"transp": "transporte",
	"pap": "papeleria",
}

_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def normalize(text: str) -> str:
	"""
	Normaliza texto para matching semantico:
	lowercase -> sin acentos -> tokeniza -> expande abreviaturas -> elimina stopwords y tokens <2 chars.
	"""
	if not text:
		return ""
	t = text.lower()
	t = unicodedata.normalize("NFD", t)
	t = "".join(c for c in t if unicodedata.category(c) != "Mn")
	tokens = _TOKEN_RE.split(t)
	result = []
	for tok in tokens:
		if not tok or len(tok) < 2:
			continue
		tok = _ABBREVS.get(tok, tok)
		if tok not in _STOPWORDS:
			result.append(tok)
	return " ".join(result)


def keywords_match(text: str, keywords_csv: str) -> bool:
	"""True si TODOS los keywords normalizados aparecen en el texto normalizado."""
	if not keywords_csv or not text:
		return False
	norm_text = normalize(text)
	for kw in keywords_csv.split(","):
		kw_norm = normalize(kw.strip())
		if kw_norm and kw_norm not in norm_text:
			return False
	return True
