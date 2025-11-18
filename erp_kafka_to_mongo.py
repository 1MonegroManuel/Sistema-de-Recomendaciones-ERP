# erp_kafka_to_mongo.py
# ------------------------------------------------------------
# Consume mensajes de Kafka y los almacena en MongoDB Atlas.
# Cada tópico se guarda en una colección: erp.products, erp.customers, etc.
# ------------------------------------------------------------
from kafka import KafkaConsumer
from pymongo import MongoClient, UpdateOne
import json, time
import ast
from config import MONGODB_CONNECTION_STRING, KAFKA_BOOTSTRAP_SERVERS, MONGODB_DATABASE, COLLECTIONS

BROKER = KAFKA_BOOTSTRAP_SERVERS
MONGO_URI = MONGODB_CONNECTION_STRING
DB_NAME = MONGODB_DATABASE

TOPICS = ["erp.products", "erp.customers", "erp.sales", "erp.sales_items"]

def get_mongo():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def ensure_json(v):
    if v is None:
        return None
    # bytes/str -> intentar JSON, si falla intentar literal Python
    if isinstance(v, (bytes, bytearray)):
        s = v.decode("utf-8", errors="replace")
    elif isinstance(v, str):
        s = v
    else:
        return v
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except Exception:
            return s

def main():
    consumer = KafkaConsumer(
        *TOPICS,
        bootstrap_servers=BROKER,
        value_deserializer=lambda v: ensure_json(v),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="erp-sink-mongo",
        consumer_timeout_ms=30000,
        max_poll_records=1000
    )

    db = get_mongo()
    collections = {t: db[t.replace("erp.", "")] for t in TOPICS}
    BATCH = 1000
    buffers = {t: [] for t in TOPICS}

    print("📥 Esperando mensajes de Kafka...")
    try:
        while True:
            records_batch = consumer.poll(timeout_ms=1000)
            for msgs in records_batch.values():
                for rec in msgs:
                    topic = rec.topic
                    doc = rec.value
                    # ignorar los mensajes 'init'
                    if isinstance(doc, dict) and doc.get("init") is True:
                        continue
                    buffers[topic].append(doc)

            # flush por lote
            for t, docs in buffers.items():
                if len(docs) >= BATCH:
                    col = collections[t]
                    ops = []
                    pk = None
                    if t == "erp.products": pk = "product_id"
                    elif t == "erp.customers": pk = "customer_id"
                    elif t == "erp.sales": pk = "sale_id"
                    elif t == "erp.sales_items": pk = ["sale_id", "line_n"]

                    for d in docs:
                        if pk is None:
                            continue
                        if isinstance(pk, list):
                            q = {k: d[k] for k in pk}
                        else:
                            q = {pk: d[pk]}
                        ops.append(UpdateOne(q, {"$set": d}, upsert=True))
                    if ops:
                        col.bulk_write(ops, ordered=False)
                        print(f"💾 Guardados {len(ops)} docs en {col.name}")
                    buffers[t].clear()

    except KeyboardInterrupt:
        print("Interrumpido por el usuario.")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
