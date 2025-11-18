# model_train_reco.py
# Entrena un modelo de recomendaciones item-based (co-ocurrencia + coseno)
# Fuente: MongoDB Atlas (colección sales_items). Salida: models/item_sim.pkl

import os, math, pickle
from datetime import datetime
from collections import defaultdict, Counter

from pymongo import MongoClient
from config import MONGODB_CONNECTION_STRING, MONGODB_DATABASE

MONGO_URI = MONGODB_CONNECTION_STRING  # ✅ Usa MongoDB Atlas
DB_NAME   = MONGODB_DATABASE          # ✅ Usa erp_database (donde están tus datos)
DET_COLL  = "sales_items"             # ✅ Colección correcta

OUT_DIR   = "models"
OUT_PATH  = os.path.join(OUT_DIR, "item_sim.pkl")

# Hiperparámetros del trainer
RECENCY_HALFLIFE_MONTHS = 6       # decaimiento temporal (más peso a lo reciente)
MIN_SUPPORT             = 5       # soporte mínimo para considerar un item en similitudes
TOP_SIM_PER_ITEM        = 100     # recorte de vecinos por item para compactar

def time_decay_weight(ts: datetime, ref: datetime, half_life_m=RECENCY_HALFLIFE_MONTHS):
    """Pondera por recencia: cada 'half_life' meses el peso se reduce a la mitad."""
    if not isinstance(ts, datetime): 
        return 1.0
    months = (ref.year - ts.year) * 12 + (ref.month - ts.month)
    return 0.5 ** (months / float(half_life_m)) if half_life_m > 0 else 1.0

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    db = MongoClient(MONGO_URI)[DB_NAME]

    # 1) Leemos cestas (venta -> lista de product_id)
    print("Cargando histórico desde Mongo…")
    # Unimos con cabecera si existe para obtener fecha de la venta
    # Si no tienes 'sales' con la fecha, usa 'fecha_sistema' del detalle si está.
    sales = {d["sale_id"]: d for d in db.sales.find({}, {"sale_id":1,"sale_datetime":1})}
    baskets = defaultdict(list)
    basket_time = {}

    for det in db[DET_COLL].find({}, {"sale_id":1, "product_id":1, "quantity":1, "net_amount":1}):
        sid = det["sale_id"]
        pid = int(det["product_id"])
        qty = det.get("quantity", 1)
        baskets[sid].extend([pid]*int(qty if qty and qty>0 else 1))
        # timestamp
        ts = None
        if sid in sales:
            ts = sales[sid].get("sale_datetime")
        else:
            ts = det.get("fecha_sistema") or det.get("sale_datetime")
        if sid not in basket_time:
            basket_time[sid] = ts

    if not baskets:
        print(f"No hay datos en {DET_COLL} en la base de datos {DB_NAME}.")
        print("Verifica que los datos estén cargados en MongoDB Atlas.")
        return

    ref_time = max([t for t in basket_time.values() if isinstance(t, datetime)] or [datetime.utcnow()])
    print(f"Ventas únicas: {len(baskets)} | Ref time: {ref_time}")

    # 2) Conteos: ocurrencia por item y co-ocurrencia por par
    item_count = Counter()
    pair_count = defaultdict(Counter)

    for sid, items in baskets.items():
        if not items: 
            continue
        w = time_decay_weight(basket_time.get(sid), ref_time)
        uniq = list(set(items))
        for i in uniq:
            item_count[i] += w
        # co-ocurrencia (pares no ordenados)
        n = len(uniq)
        for a_idx in range(n):
            for b_idx in range(a_idx+1, n):
                a, b = uniq[a_idx], uniq[b_idx]
                pair_count[a][b] += w
                pair_count[b][a] += w

    # 3) Similitud coseno item-item
    item_sim = {}
    for i, neighbors in pair_count.items():
        if item_count[i] < MIN_SUPPORT: 
            continue
        sims = []
        norm_i = math.sqrt(item_count[i])
        for j, cij in neighbors.items():
            if item_count[j] < MIN_SUPPORT: 
                continue
            sim = cij / (norm_i * math.sqrt(item_count[j]) + 1e-9)
            sims.append((j, float(sim)))
        sims.sort(key=lambda x: x[1], reverse=True)
        item_sim[i] = sims[:TOP_SIM_PER_ITEM]

    # 4) Guardar
    with open(OUT_PATH, "wb") as f:
        pickle.dump({"item_sim": item_sim, "item_count": dict(item_count)}, f)

    print(f"✅ Modelo guardado en {OUT_PATH} | Items con vecinos: {len(item_sim)}")

if __name__ == "__main__":
    main()
