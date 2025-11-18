# reco_service_stream.py
# Servicio en tiempo real: consume ventas, genera recomendaciones y publica a Kafka

import json, pickle, time, signal, sys
from pathlib import Path
from typing import List, Dict
from kafka import KafkaConsumer, KafkaProducer
from pymongo import MongoClient
from datetime import datetime
sys.path.append(str(Path(__file__).parent.parent))
from config.config import MONGODB_CONNECTION_STRING, MONGODB_DATABASE, KAFKA_BOOTSTRAP_SERVERS

# Variable global para manejar señales de interrupción
shutdown_flag = False

def signal_handler(sig, frame):
    """Maneja Ctrl+C correctamente"""
    global shutdown_flag
    print("\n\n🛑 Señal de interrupción recibida. Deteniendo...")
    shutdown_flag = True
    sys.exit(0)

# Registrar el manejador de señales
signal.signal(signal.SIGINT, signal_handler)

BROKER     = KAFKA_BOOTSTRAP_SERVERS  # ✅ Usa config.py
TOPIC_SALES= "erp.sales"             # cabezal de venta (ya lo tienes en práctica 3)
TOPIC_RECO = "erp.recommendations"   # nuevo tópico para recomendaciones

MONGO_URI  = MONGODB_CONNECTION_STRING  # ✅ Usa MongoDB Atlas
DB_NAME    = MONGODB_DATABASE          # ✅ Usa erp_database (donde están tus datos)
DET_COLL   = "sales_items"             # ✅ Colección correcta
RECO_COLL  = "recommendations"         # ✅ Colección para guardar recomendaciones

MODEL_PATH = str(Path(__file__).parent.parent / "data" / "models" / "item_sim.pkl")
TOP_N      = 5

# ------- util -------
def load_model(path=MODEL_PATH):
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["item_sim"], data["item_count"]

def get_basket_products(db, sale_id: int) -> List[int]:
    rows = list(db[DET_COLL].find({"sale_id": int(sale_id)}, {"product_id":1}))
    return [int(r["product_id"]) for r in rows if "product_id" in r]

def enrich_recommendations_with_product_names(db, recommendations: List[Dict], products_cache: Dict = None) -> List[Dict]:
    """ Enriquece las recomendaciones con nombres, categorías y métricas de ML en porcentajes """
    if not recommendations:
        return []
    
    # Obtener IDs de productos únicos
    product_ids = [r.get("product_id") for r in recommendations if r.get("product_id")]
    
    if not product_ids:
        return recommendations
    
    # Calcular métricas de ML (normalizar relevancias a porcentajes)
    relevancias = [r.get("relevancia", r.get("score", 0.0)) for r in recommendations]  # Compatibilidad: acepta "score" o "relevancia"
    max_relevancia = max(relevancias) if relevancias else 1.0
    min_relevancia = min(relevancias) if relevancias else 0.0
    relevancia_range = max_relevancia - min_relevancia if max_relevancia > min_relevancia else 1.0
    
    # Cargar productos que no estén en el cache
    products_to_fetch = []
    if products_cache is None:
        products_cache = {}
    
    for pid in product_ids:
        if pid not in products_cache:
            products_to_fetch.append(pid)
    
    # Consultar MongoDB solo para productos que no están en cache
    if products_to_fetch:
        fetched = db.products.find(
            {"product_id": {"$in": products_to_fetch}},
            {"product_id": 1, "name": 1, "category": 1}
        )
        for p in fetched:
            pid = int(p.get("product_id", 0))
            products_cache[pid] = {
                "name": p.get("name", f"Producto #{pid}"),
                "category": p.get("category", "Sin categoría")
            }
    
    # Enriquecer recomendaciones con nombres y métricas de ML
    enriched = []
    total_recommendations = len(recommendations)
    
    for idx, r in enumerate(recommendations):
        pid = r.get("product_id")
        relevancia = r.get("relevancia", r.get("score", 0.0))  # Compatibilidad: acepta "score" o "relevancia"
        product_info = products_cache.get(pid, {})
        
        # Calcular métricas de ML en porcentajes
        # Relevancia normalizada a porcentaje (0-100%)
        relevancia_percentage = ((relevancia - min_relevancia) / relevancia_range * 100.0) if relevancia_range > 0 else 0.0
        
        # Confianza basada en la relevancia (más alto = más confianza)
        confidence_percentage = min(100.0, relevancia_percentage * 1.2)  # Ajustar para que max sea 100%
        
        # Ranking normalizado (1 = mejor, porcentaje invertido)
        ranking = idx + 1
        ranking_percentage = ((total_recommendations - ranking + 1) / total_recommendations * 100.0) if total_recommendations > 0 else 0.0
        
        enriched_rec = {
            "product_id": pid,
            "product_name": product_info.get("name", f"Producto #{pid}"),
            "category": product_info.get("category", "Sin categoría"),
            "relevancia": relevancia,  # Relevancia original (compatibilidad: mantener "score" también)
            "score": relevancia,  # Mantener para compatibilidad hacia atrás
            "relevancia_percentage": round(relevancia_percentage, 2),  # Relevancia en porcentaje
            "score_percentage": round(relevancia_percentage, 2),  # Compatibilidad: mantener también "score_percentage"
            "confidence_percentage": round(confidence_percentage, 2),  # Confianza en porcentaje
            "ranking": ranking,  # Ranking (1 = mejor)
            "ranking_percentage": round(ranking_percentage, 2)  # Ranking en porcentaje
        }
        enriched.append(enriched_rec)
    
    return enriched

def recommend_for_basket(item_sim: Dict[int, List], basket: List[int], k=TOP_N) -> List[Dict]:
    basket_uniq = set(basket)
    relevancias = {}  # producto -> relevancia acumulada
    for pid in basket_uniq:
        neighbors = item_sim.get(pid, [])
        for nb, sim in neighbors:
            if nb in basket_uniq: 
                continue  # no recomendar algo ya comprado
            relevancias[nb] = relevancias.get(nb, 0.0) + sim
    # top-k
    ranked = sorted(relevancias.items(), key=lambda x: x[1], reverse=True)[:k]
    return [{"product_id": int(p), "relevancia": float(s), "score": float(s)} for p, s in ranked]  # Mantener "score" para compatibilidad

def main():
    print("Cargando modelo…")
    try:
        item_sim, item_count = load_model()
        print(f"✅ Modelo cargado. Items con vecinos: {len(item_sim)}")
    except FileNotFoundError:
        print(f"❌ Error: No se encuentra el modelo en {MODEL_PATH}")
        print("   Ejecuta primero: python model_train_reco.py")
        return
    except Exception as e:
        print(f"❌ Error cargando modelo: {e}")
        return

    print(f"Conectando a MongoDB Atlas ({DB_NAME})...")
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command('ping')  # Verificar conexión
        db = client[DB_NAME]
        print(f"✅ Conectado a MongoDB Atlas | Base de datos: {DB_NAME}")
    except Exception as e:
        print(f"❌ Error conectando a MongoDB Atlas: {e}")
        print(f"   Verifica tu conexión a internet y las credenciales en config.py")
        return
    
    # Cache de productos para enriquecer recomendaciones (evita consultas repetidas)
    products_cache = {}
    print(f"✅ Cache de productos inicializado (se cargarán productos bajo demanda)")

    # Usar un group_id único para leer todos los mensajes disponibles
    group_id = f"reco-service-{int(time.time())}"
    
    print(f"🔌 Configurando consumer Kafka...")
    print(f"   - Tópico: {TOPIC_SALES}")
    print(f"   - Broker: {BROKER}")
    print(f"   - Group ID: {group_id}")
    
    consumer = KafkaConsumer(
        TOPIC_SALES,
        bootstrap_servers=BROKER,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=group_id,
        consumer_timeout_ms=5000,
        max_poll_records=20  # ✅ Procesar solo 20 mensajes a la vez para no bloquearse
    )
    
    # Esperar a que el consumer se suscriba
    print(f"⏳ Suscribiéndose al tópico...")
    time.sleep(2)
    
    print(f"🔌 Configurando producer Kafka...")
    print(f"   - Tópico destino: {TOPIC_RECO}")
    print(f"   - Broker: {BROKER}")
    
    producer = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        acks="0",  # ✅ Cambiar a "0" para que no espere confirmación (más rápido)
        linger_ms=50,  # Esperar hasta 50ms para agrupar mensajes
        batch_size=16384,  # 16KB de batch (más pequeño para evitar bloqueos)
        compression_type=None,  # ✅ Sin compresión para reducir latencia
        request_timeout_ms=30000,  # Timeout de 30 segundos para requests
        max_in_flight_requests_per_connection=5,  # Permitir múltiples requests en vuelo
        retries=0,  # ✅ Sin reintentos para evitar acumulación
        max_block_ms=10000,  # ✅ Esperar hasta 10 segundos antes de fallar al enviar
        buffer_memory=67108864  # ✅ 64MB de buffer (por defecto)
    )
    
    print(f"✅ Producer Kafka creado correctamente")

    print(f"✅ Conectado a Kafka | Broker: {BROKER}")
    print(f"📥 Esperando ventas en '{TOPIC_SALES}' …")
    print(f"📤 Publicando recomendaciones en '{TOPIC_RECO}'")
    print(f"💡 Leyendo TODOS los mensajes disponibles (desde el principio)")
    print(f"{'='*60}")
    
    msg_count = 0
    last_heartbeat = time.time()
    last_flush_time = time.time()
    FLUSH_INTERVAL = 5.0  # Hacer flush cada 5 segundos en lugar de después de cada batch
    try:
        while not shutdown_flag:
            polled = consumer.poll(timeout_ms=1000)
            if not polled:
                # No hay mensajes, mostrar heartbeat cada 15 segundos
                current_time = time.time()
                if current_time - last_heartbeat >= 15:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"💓 [{timestamp}] Esperando ventas... (procesadas: {msg_count})")
                    last_heartbeat = current_time
                continue
            
            # Mensajes recibidos
            total_msgs = sum(len(recs) for recs in polled.values())
            print(f"📨 Recibido lote de {total_msgs} mensaje(s)")
                
            for tp, recs in polled.items():
                batch_size = len(recs)
                print(f"   📦 Procesando {batch_size} mensaje(s) de partición {tp.partition}")
                processed_in_batch = 0
                errors_in_batch = 0
                for idx, rec in enumerate(recs, 1):
                    try:
                        msg_count += 1
                        sale = rec.value
                        
                        # Mostrar progreso cada 50 mensajes dentro del batch
                        if idx % 50 == 0 or idx == batch_size:
                            print(f"      ⏳ Progreso: {idx}/{batch_size} mensajes procesados en este batch...")
                        
                        if sale is None:
                            print(f"⚠️  [{msg_count}] Mensaje None recibido")
                            continue
                            
                        if not isinstance(sale, dict):
                            print(f"⚠️  [{msg_count}] Mensaje no es un dict: {type(sale)}")
                            continue
                        
                        # se espera un 'sale_id' en el mensaje de erp.sales
                        sale_id = sale.get("sale_id") or sale.get("id")
                        if not sale_id:
                            print(f"⚠️  [{msg_count}] Mensaje sin sale_id: {list(sale.keys())[:5]}...")
                            continue

                        sale_id = int(sale_id)
                        basket = get_basket_products(db, sale_id)
                        
                        if not basket:
                            # si todavía no están los items, intenta más tarde (puede venir desfasado)
                            time.sleep(0.3)
                            basket = get_basket_products(db, sale_id)
                            if not basket:
                                print(f"⚠️  [{msg_count}] No se encontraron productos para sale_id={sale_id}")
                                continue

                        reco = recommend_for_basket(item_sim, basket, k=TOP_N)
                        
                        # ✅ Enriquecer recomendaciones con nombres de productos y métricas de ML
                        reco_enriched = enrich_recommendations_with_product_names(db, reco, products_cache)
                        
                        # ✅ Obtener customer_id del mensaje de venta o de la base de datos
                        customer_id = sale.get("customer_id")
                        if not customer_id:
                            # Intentar obtener desde la base de datos
                            sale_doc = db.sales.find_one({"sale_id": sale_id}, {"customer_id": 1})
                            if sale_doc:
                                customer_id = sale_doc.get("customer_id")
                        
                        payload = {
                            "sale_id": sale_id,
                            "customer_id": customer_id,  # ✅ Añadir customer_id al payload
                            "timestamp": sale.get("sale_datetime") or sale.get("fecha_venta"),
                            "basket_products": list(map(int, basket)),
                            "recommendations": reco_enriched,  # ✅ Ya incluye nombres y categorías
                            "algo": "itemcf_cosine_v1",
                            "created_at": datetime.now().isoformat()  # Agregar timestamp de creación
                        }
                        
                        # ✅ GUARDAR EN MONGODB (respaldo/alternativa)
                        try:
                            db[RECO_COLL].update_one(
                                {"sale_id": sale_id},
                                {"$set": payload},
                                upsert=True
                            )
                            processed_in_batch += 1
                        except Exception as e:
                            print(f"⚠️  [{msg_count}] Error guardando en MongoDB: {e}")
                        
                        # Enviar a Kafka también (intento, pero MongoDB es el respaldo)
                        try:
                            future = producer.send(TOPIC_RECO, payload)
                            # Log solo para los primeros mensajes o cada 50 para confirmar envío
                            if processed_in_batch <= 3 or processed_in_batch % 50 == 0:
                                timestamp = datetime.now().strftime("%H:%M:%S")
                                print(f"📤 [{timestamp}] Enviando recomendación para sale_id={sale_id} a Kafka y MongoDB (total procesadas: {processed_in_batch})")
                        except Exception as e:
                            # Error en Kafka no es crítico si ya guardamos en MongoDB
                            if processed_in_batch <= 5:
                                print(f"⚠️  [{msg_count}] Error enviando a Kafka (pero guardado en MongoDB): {e}")
                            continue
                        last_heartbeat = time.time()
                        
                        # Solo mostrar los primeros 3 mensajes y luego cada 50
                        if processed_in_batch <= 3 or processed_in_batch % 50 == 0:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            print(f"✅ [{timestamp}] #{msg_count} sale_id={sale_id} | basket={basket[:5]}… | reco={[r['product_id'] for r in reco[:3]]}")
                    except Exception as e:
                        errors_in_batch += 1
                        if errors_in_batch <= 5:  # Solo mostrar los primeros 5 errores
                            print(f"❌ [{msg_count}] Error procesando mensaje: {e}")
                            import traceback
                            traceback.print_exc()
                        continue
                
                # Flush al final del batch - IMPORTANTE para asegurar envío
                # Con acks="0" esto debería ser rápido. El flush asegura que los mensajes
                # en el buffer se envíen al broker de Kafka.
                if processed_in_batch > 0:  # Solo hacer flush si hay mensajes procesados
                    flush_start = time.time()
                    try:
                        producer.flush(timeout=10.0)  # Timeout de 10 segundos
                        flush_time = time.time() - flush_start
                        last_flush_time = time.time()
                        if flush_time > 2.0:  # Si tarda más de 2 segundos, advertir
                            print(f"   ⚠️  Flush tardó {flush_time:.2f} segundos")
                    except Exception as e:
                        # Si el flush falla, es crítico - los mensajes no se enviaron
                        print(f"   ❌ Error crítico en flush: {type(e).__name__}: {e}")
                        # Intentar un último flush con timeout más corto
                        try:
                            producer.flush(timeout=1.0)
                        except:
                            print(f"   ❌ Flush falló completamente. Los mensajes pueden no haberse enviado.")
                
                # Resumen del batch procesado
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"   ✅ [{timestamp}] Batch completado: {processed_in_batch} exitosos, {errors_in_batch} errores de {batch_size} mensajes")
            # loop
    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print(f"🛑 Interrumpido por usuario.")
        print(f"📊 Total de mensajes procesados: {msg_count}")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔌 Cerrando conexiones...")
        producer.flush()
        producer.close()
        consumer.close()
        print("✅ Servicio detenido correctamente.")

if __name__ == "__main__":
    main()
