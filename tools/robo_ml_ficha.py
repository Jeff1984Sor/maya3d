"""Robô do dono: completa a ficha técnica dos anúncios do ML (ficha incompleta perde busca).

1) --levantar : lê a ficha de cada anúncio publicado (o que falta + valores aceitos) e salva em
                ~/Downloads/robo-ficha.json, com um resumo por atributo faltando.
2) aplicar    : preenche só com o que se sabe de verdade da peça — medidas e peso do pipeline 3D,
                cor do filamento, PLA, kit/unidade, "não" para recursos que peça de PLA não tem
                (luz, som, pilha, Wi-Fi...) — e com ~/Downloads/robo-ficha-regras.json:
                {"*": {"ATRIBUTO": "valor"}, "MLB1234": {...}, "produto:215": {...}}
                Valor de lista fechada é casado pelo nome; se não casar, não manda.
                Números de registro (INMETRO, Anatel, CONAMA, MAPA...) nunca são inventados.

    python tools/robo_ml_ficha.py --api https://api.<dominio> --levantar
    python tools/robo_ml_ficha.py --api https://api.<dominio> [--dry-run] [--so-produto 215]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import time
import unicodedata
from typing import Any

import httpx

DOWNLOADS = pathlib.Path.home() / "Downloads"
SURVEY = DOWNLOADS / "robo-ficha.json"
RULES = DOWNLOADS / "robo-ficha-regras.json"

# medidas da peça (bbox do pipeline 3D: x, y, z em mm) — mesma leitura das fotos de medidas
DIMS = {
    "WIDTH": 0,
    "TOTAL_WIDTH": 0,
    "NATIVITY_SCENE_WIDTH": 0,
    "LENGTH": 1,
    "DEPTH": 1,
    "NATIVITY_SCENE_LENGTH": 1,
    "HEIGHT": 2,
    "TOTAL_HEIGHT": 2,
    "NATIVITY_SCENE_HEIGHT": 2,
}
MATERIALS = (
    "MATERIAL",
    "MATERIALS",
    "MAIN_MATERIAL",
    "STRUCTURE_MATERIAL",
    "CANDLE_HOLDER_MATERIAL",
    "CHRISTMAS_TREE_MATERIALS",
    "CHRISTMAS_TREE_BASE_MATERIAL",
    "NATIVITY_SCENE_MATERIAL",
    "FIGURES_MATERIAL",
    "PAINTING_FRAME_MATERIAL",
)
COLORS = ("COLOR", "FRAME_COLOR", "STRUCTURE_COLOR")
UNITS = ("UNITS_PER_PACK", "UNITS_PER_PACKAGE", "PIECES_NUMBER", "DECORATIVE_NO_LIGHT_SIGNS_NUMBER")
# peça de PLA sem eletrônica nem acessório: estes recursos ela não tem
NO = (
    "WITH_LIGHT",
    "WITH_LIGHTS",
    "IS_LED",
    "WITH_SOUND",
    "WITH_SOUNDS",
    "WITH_WI_FI",
    "WITH_WI_FI_CONNECTION",
    "WITH_TIMER",
    "IS_AUTOMATIC",
    "WITH_RECHARGEABLE_BATTERY",
    "REQUIRES_CELL_BATTERIES",
    "WITH_BUILT_IN_CAMERA",
    "INCLUDES_REMOTE_CONTROL",
    "WITH_USB_PORT",
    "WITH_WHEELS",
    "INCLUDES_CATNIP",
    "WITH_GLASS",
    "WITH_MAGNET",
    "WITH_GEMSTONE",
    "INCLUDES_BOX",
    "WITH_FOLDABLE_LEGS",
    "WITH_SELF_WATERING_SYSTEM",
    "IS_DISPOSABLE",
    "IS_DISHWASHER_SAFE",
    "WITH_SILENCER",
    "WITH_QR_CODE",
    "WITH_SILICONE_BASE",
    "WITH_ADJUSTABLE_HEIGHT",
    "WITH_ROTATING_HEAD",
    "INCLUDES_UMBRELLA_STAND",
    "WITH_CEL_SUPPORT",
    "IS_FOLDABLE",
    "WITH_TOY",
    "WITH_HOUSE",
    "IS_MASSAGING_BRUSH",
    "IS_DESHEDDER_BRUSH",
    "INCLUDES_ACCESSORIES",
    "WITH_SPRING",
    "IS_HANGING",
)
# "não se aplica" (value_id -1): campos de produto elétrico/regulado que a peça de PLA não tem.
# Declarar N/A completa a ficha sem inventar número de registro.
NOT_APPLICABLE = (
    "VOLTAGE",
    "BATTERY_VOLTAGE",
    "CELL_BATTERY_TYPE",
    "CELL_BATTERIES_TYPE",
    "TOY_CELL_BATTERIES_TYPE",
    "REMOTE_CONTROL_BATTERIES_TYPE",
    "COMPATIBLE_VIRTUAL_ASSISTANTS",
    "COMPATIBLE_OPERATING_SYSTEMS",
    "ANATEL_HOMOLOGATION_NUMBER",
    "ANATEL_HOMOLOGATION_LABEL",
    "CONAMA_LICENSE_NUMBER",
    "AFE_CERTIFICATION_NUMBER",
    "MAPA_PRODUCT_REGISTRATION_NUMBER",
    "INMETRO_CERTIFICATION_REGISTRATION_NUMBER",
    "INMETRO_CONFORMITY_SEAL",
    "ALPHANUMERIC_MODELS",
    "FILTERS_NUMBER",
    "BATTERY_AUTONOMY",
    "CAMERA_RESOLUTION",
    "POWER_SUPPLY_TYPES",
    "WIRELESS_POWER_SUPPLY_TYPE",
    "SCENT",
    "DURATION",
    "CANDLE_CAPACITY",
    "GEMSTONE_TYPE",
    "UPHOLSTERY_MATERIAL",
    "BRISTLES_MATERIAL",
    "CHARACTERS",
)
FIXED = {
    "POWER_SUPPLY_TYPE": "Operação manual",
    "FINISH": "Fosco",
    "RECOMMENDED_USE": "Interior",
    "PANEL_TYPE": "Painel único",
    "PLANT_POT_TYPE": "Vaso de plantas",
    "TRAY_TYPE": "Para o lar",
    "IS_TABLE_CHRISTMAS_TREE": "Sim",
}
RELIGIOUS = (
    "jesus",
    "nossa senhora",
    "santo",
    "santa ",
    "sao ",
    "anjo",
    "maria",
    "cristo",
    "sagrad",
    "terco",
    "orac",
    "pastor",
    "davi",
    "biblia",
)


def norm(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(raw.lower().split())


def pick(attr: dict[str, Any], wanted: str) -> dict[str, str] | None:
    """Valor para um atributo: de lista casa pelo nome; texto/número vai como está."""
    values = attr.get("values") or []
    if values:
        target = norm(wanted)
        for v in values:
            if norm(v["name"]) == target:
                return {"id": attr["id"], "value_id": str(v["id"])}
        if attr.get("value_type") in ("list", "boolean"):
            return None  # lista fechada: valor fora dela o ML recusa
    return {"id": attr["id"], "value_name": wanted}


def unit_of(attr: dict[str, Any], prefer: str) -> str:
    units = attr.get("allowed_units") or []
    return prefer if prefer in units or not units else str(units[0])


def length(attr: dict[str, Any], mm: float) -> str | None:
    unit = unit_of(attr, "cm")
    if unit == "cm":
        return f"{max(mm, 1) / 10:.1f} cm"
    if unit == "mm":
        return f"{max(round(mm), 1)} mm"
    return None


class Piece:
    """O que se sabe de verdade da peça: medidas, peso, cor do filamento, kit, nicho."""

    def __init__(
        self, product: dict[str, Any], variant: dict[str, Any], colors: dict[str, Any]
    ) -> None:
        self.title = norm(product.get("title"))
        self.niche = str(product.get("niche") or "")
        self.dims = [float(d) for d in variant.get("dims_mm") or []]
        grams = {str(k): float(v) for k, v in (variant.get("grams_by_material") or {}).items()}
        self.grams = sum(grams.values())
        main = max(grams, key=lambda k: grams[k]) if grams else None
        several = len(grams) > 1 or len(set((variant.get("color_by_part") or {}).values())) > 1
        self.color = colors.get(main) if main and not several else None  # várias cores: não diz
        kit = (variant.get("params") or {}).get("kit") or []
        count = re.match(r"kit (\d+)", self.title)
        self.units = sum(int(e[1]) for e in kit) if kit else (int(count.group(1)) if count else 1)
        self.kit = bool(kit) or self.title.startswith("kit ")
        self.personal = bool(product.get("customizable")) or self.has("personalizad", "com nome")

    def has(self, *words: str) -> bool:
        return any(w in self.title for w in words)


def _number(attr: dict[str, Any], piece: Piece) -> dict[str, str] | None:
    aid = attr["id"]
    if len(piece.dims) != 3:
        return None
    x, y, _ = piece.dims
    value: str | None = None
    if aid in DIMS:
        value = length(attr, piece.dims[DIMS[aid]])
    elif aid == "MAX_CHRISTMAS_TREE_WIDTH" or (
        aid == "DIAMETER" and abs(x - y) <= 0.08 * max(x, y)  # diâmetro só de peça redonda
    ):
        value = length(attr, max(x, y))
    elif aid == "THICKNESS":
        value = length(attr, min(piece.dims))
    elif aid == "WEIGHT" and piece.grams > 0 and unit_of(attr, "g") == "g":
        value = f"{max(round(piece.grams), 1)} g"
    return {"id": aid, "value_name": value} if value else None


def _by_title(attr: dict[str, Any], piece: Piece) -> dict[str, str] | None:
    aid = attr["id"]
    name: str | None = None
    if aid == "SCULPTURE_TYPE":
        name = "Relevo" if piece.has("relevo") else "Estátua"
    elif aid == "SCULPTURE_THEME":
        if piece.niche == "pet":
            name = "Animais"
        elif piece.has(*RELIGIOUS):
            name = "Religião"
    elif aid in ("DOG_AND_CAT_DRINKER_AND_FEEDER_PRODUCT_TYPE", "BIRD_DRINKER_AND_FEEDER_FUNCTION"):
        drink = piece.has("bebedouro", "agua")
        feed = piece.has("comedouro", "tigela", "prato", "racao", "petisco")
        if drink and feed:
            name = "Bebedouro/Comedouro"
        elif drink or feed:
            name = "Bebedouro" if drink else "Comedouro"
    elif aid == "RECOMMENDED_PETS":
        cat, dog = piece.has("gato", "felin"), piece.has("cao ", "caes", "cachorr", "dog")
        if cat or dog:
            name = "Cão e Gato" if cat and dog else ("Gato" if cat else "Cão")
    elif aid == "CHRISTMAS_DOLLS_TYPES":
        for word, label in (
            ("rena", "Rena"),
            ("papai noel", "Papai Noel"),
            ("boneco de neve", "Boneco de neve"),
        ):
            if word in piece.title:
                name = label
                break
    elif aid in ("COAT_RACK_HOOKS_NUMBER", "KEYS_NUMBER"):
        m = re.search(r"(\d+) ganchos", piece.title)
        return {"id": aid, "value_name": m.group(1)} if m else None
    elif aid == "COMPARTMENTS_NUMBER":
        m = re.search(r"(\d+) (divisorias|compartimentos|divis)", piece.title)
        return {"id": aid, "value_name": m.group(1)} if m else None
    return pick(attr, name) if name else None


def auto(attr: dict[str, Any], piece: Piece, maker: str) -> dict[str, str] | None:
    aid = attr["id"]
    if aid in NOT_APPLICABLE:
        return {"id": aid, "value_id": "-1"}
    if aid in COLORS:
        return pick(attr, str(piece.color)) if piece.color else None
    if aid in MATERIALS:
        return pick(attr, "Plástico PLA") or pick(attr, "Plástico")
    if attr.get("value_type") == "number_unit":
        return _number(attr, piece)
    if aid in UNITS:
        return {"id": aid, "value_name": str(piece.units)}
    if aid == "PACKS_NUMBER":
        return {"id": aid, "value_name": "1"}
    if aid == "MANUFACTURER":
        return {"id": aid, "value_name": maker} if maker else None
    yes_no = {
        "SALE_FORMAT": "Pack" if piece.kit else "Unidade",
        "IS_SET": "Sim" if piece.kit else "Não",
        "IS_PERSONALIZED_PRODUCT": "Sim" if piece.personal else "Não",
        "IS_CUSTOMIZED": "Sim" if piece.personal else "Não",
        "IS_DOUBLE": "Sim" if piece.has("duplo", "dupla") else "Não",
    }
    if aid in yes_no:
        return pick(attr, yes_no[aid])
    if aid == "IS_HANGABLE" and piece.has("enfeite", "pendur"):
        return pick(attr, "Sim")
    if aid == "WITH_LID" and piece.has("tampa"):
        return pick(attr, "Sim")
    if aid in NO:
        return pick(attr, "Não")
    if aid in FIXED:
        return pick(attr, FIXED[aid])
    return _by_title(attr, piece)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--levantar", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--so-produto", type=int, action="append", default=[])
    ap.add_argument("--conta-nova-desde", type=int, default=157)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    token = (DOWNLOADS / "robo-token.txt").read_text().strip()
    c = httpx.Client(
        base_url=f"{args.api.rstrip('/')}/v1/admin", headers={"x-robot-token": token}, timeout=120
    )
    listings = [
        x
        for x in c.get("/mercadolivre/listings").json()
        if x["status"] == "publicado"
        and x["id"] > args.conta_nova_desde
        and (not args.so_produto or x["product_id"] in args.so_produto)
    ]
    print(f"{len(listings)} anúncio(s)")

    if args.levantar:
        survey: dict[str, Any] = {}
        tally: collections.Counter[tuple[str, str]] = collections.Counter()
        for x in listings:
            r = c.get(f"/mercadolivre/listings/{x['id']}/attributes")
            if r.status_code != 200:
                print("x", x["external_id"], r.text[:160])
                continue
            data = r.json()
            survey[str(x["id"])] = data
            for m in data["missing"]:
                tally[(m["id"], m["name"])] += 1
            perf = data.get("performance") or {}
            print(f"  {x['external_id']} faltam {len(data['missing'])} | nota {perf.get('score')}")
            time.sleep(0.2)
        SURVEY.write_text(json.dumps(survey, ensure_ascii=False), encoding="utf-8")
        print("\nfaltando (anúncios):")
        for (aid, name), n in tally.most_common():
            print(f"  {n:4} {aid} — {name}")
        print(f"\nsalvo em {SURVEY}")
        return 0

    rules: dict[str, dict[str, str]] = (
        json.loads(RULES.read_text(encoding="utf-8")) if RULES.exists() else {}
    )
    colors = {str(m["id"]): m.get("color_name") for m in c.get("/materials").json()}
    maker = str(c.get("/brand").json().get("name") or "")
    products: dict[int, dict[str, Any]] = {}
    sent = skipped = fails = 0
    for x in listings:
        r = c.get(f"/mercadolivre/listings/{x['id']}/attributes")
        if r.status_code != 200:
            fails += 1
            print("x", x["external_id"], r.text[:160])
            continue
        data = r.json()
        pid = x["product_id"]
        if pid not in products:
            products[pid] = c.get(f"/products/{pid}").json()
        variant = next(
            (v for v in products[pid]["variants"] if v["id"] == x["variant_id"]),
            products[pid]["variants"][0],
        )
        piece = Piece(products[pid], variant, colors)
        wanted = {
            **rules.get("*", {}),
            **rules.get(data["category_id"], {}),
            **rules.get(f"produto:{pid}", {}),
        }
        fill = []
        for attr in data["missing"]:
            value = pick(attr, wanted[attr["id"]]) if attr["id"] in wanted else None
            value = value or auto(attr, piece, maker)
            if value:
                fill.append(value)
        if not fill:
            skipped += 1
            continue
        line = f"{x['external_id']} {data['title'][:50]}: " + ", ".join(
            f"{a['id']}={a.get('value_name') or a.get('value_id')}" for a in fill
        )
        if args.dry_run:
            print("~", line)
            continue
        r = c.put(f"/mercadolivre/listings/{x['id']}/attributes", json={"attributes": fill})
        if r.status_code == 200:
            sent += 1
            print("+", line)
        else:
            fails += 1
            print("x", line, "→", r.text[:300])
        time.sleep(0.4)
    print(f"atualizados: {sent} | nada a preencher: {skipped} | falhas: {fails}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
