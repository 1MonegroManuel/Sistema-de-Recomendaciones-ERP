# erp_simulator_producer_final.py
# Versión final optimizada usando confluent-kafka
import csv, json, random, time
import sys
from pathlib import Path
from typing import Dict, Any
from confluent_kafka import Producer
import logging
sys.path.append(str(Path(__file__).parent.parent))
from config.config import KAFKA_BOOTSTRAP_SERVERS

# ---------- Config ----------
CSV_DIR = Path(__file__).parent.parent / "data" / "csv_out"
BROKER = KAFKA_BOOTSTRAP_SERVERS
SHUFFLE = True
EVENTS_PER_SECOND = 20  # Aumentado para mejor rendimiento
LOOP = False

TOPICS = {
    "products": "erp.products",
    "customers": "erp.customers", 
    "sales": "erp.sales",
    "sales_items": "erp.sales_items",
}

CSV_FILES = {
    "products": CSV_DIR / "products.csv",
    "customers": CSV_DIR / "customers.csv",
    "sales": CSV_DIR / "sales.csv",
    "sales_items": CSV_DIR / "sales_items.csv",
}

KEY_FIELDS = {
    "products": "product_id",
    "customers": "customer_id",
    "sales": "sale_id",
    "sales_items": "sale_id",
}

# ---------- Utilidades ----------
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def clean_data(row: Dict[str, Any]) -> Dict[str, Any]:
    """Limpia y convierte los datos para evitar errores de serialización"""
    cleaned = {}
    for key, value in row.items():
        if value is None or value == '':
            cleaned[key] = None
        elif key in ['product_id', 'customer_id', 'sale_id', 'line_n', 'stock', 'active']:
            # Campos que deben ser enteros
            try:
                cleaned[key] = int(float(str(value)))
            except (ValueError, TypeError):
                cleaned[key] = 0
        elif key in ['unit_price', 'unit_cost', 'quantity', 'total_amount', 'gross_amount', 'net_amount', 'discount_header', 'tax', 'line_discount']:
            # Campos que deben ser flotantes
            try:
                cleaned[key] = float(str(value))
            except (ValueError, TypeError):
                cleaned[key] = 0.0
        else:
            # Campos de texto
            cleaned[key] = str(value).strip()
    
    return cleaned

def read_csv_rows(path: Path) -> list:
    """Lee todas las filas del CSV y las limpia"""
    rows = []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(clean_data(row))
    except Exception as e:
        logging.getLogger(__name__).error(f"Error leyendo {path}: {e}")
    
    return rows

def delivery_callback(err, msg):
    """Callback para confirmar entrega de mensajes"""
    if err is not None:
        logging.getLogger(__name__).error(f"Error entregando mensaje: {err}")
    # No loguear cada mensaje individual para evitar spam

def make_producer() -> Producer:
    """Crea un productor confluent-kafka optimizado"""
    logger = logging.getLogger(__name__)
    logger.info(f"Conectando a Kafka en {BROKER}...")
    
    config = {
        'bootstrap.servers': BROKER,
        'client.id': 'erp-producer',
        'acks': '1',  # Confirmación de al menos un broker
        'retries': 3,
        'batch.size': 16384,  # 16KB
        'linger.ms': 10,  # Esperar 10ms para agrupar mensajes
        'compression.type': 'gzip',  # Compresión para reducir tamaño
        'max.in.flight.requests.per.connection': 5,
        'request.timeout.ms': 30000,
        'delivery.timeout.ms': 120000,
    }
    
    producer = Producer(config)
    logger.info("Productor Kafka creado exitosamente")
    return producer

def run_once(producer: Producer):
    logger = logging.getLogger(__name__)
    logger.info("CSV_DIR (abs): %s", CSV_DIR.resolve())
    
    # Verificar archivos CSV
    for name, path in CSV_FILES.items():
        exists = path.exists()
        logger.info(f"Verificando {name}: {path} -> existe={exists}")
    
    # Cargar CSVs
    buffers = {}
    for name, path in CSV_FILES.items():
        if not path.exists():
            raise FileNotFoundError(f"No existe CSV: {path.resolve()}")
        buffers[name] = read_csv_rows(path)
    
    sizes = {k: len(v) for k, v in buffers.items()}
    logger.info("Filas por CSV: %s", sizes)
    assert sizes["sales_items"] > 0, "sales_items.csv vacío o no se está leyendo."

    # Construir stream
    # ✅ PRIMERO: Enviar TODOS los productos para verificar que se guardan correctamente
    stream = []
    
    # 1. Enviar todos los productos primero (sin shuffle para mantener orden)
    logger.info("📦 Enviando primero todos los productos (%d registros)...", sizes["products"])
    for row in buffers["products"]:
        stream.append(("products", row))
    
    # 2. Luego enviar el resto de los datos (clientes, ventas, items)
    if SHUFFLE:
        # Mezclar solo los demás datos (sin productos)
        for k in ["customers", "sales", "sales_items"]:
            if k in buffers:
                random.shuffle(buffers[k])
        
        keys = ["customers", "sales", "sales_items"]
        weights = {
            "customers": max(1, sizes["customers"] // 50),
            "sales": max(1, sizes["sales"] // 3),
            "sales_items": max(1, sizes["sales_items"] // 3),
        }
        pools = {k: iter(buffers[k]) for k in keys}
        exhausted = set()
        while len(exhausted) < len(keys):
            for k in keys:
                if k in exhausted:
                    continue
                for _ in range(max(1, weights.get(k, 1))):
                    try:
                        stream.append((k, next(pools[k])))
                    except StopIteration:
                        exhausted.add(k)
                        break
    else:
        # Orden secuencial para el resto
        for k in ["customers", "sales", "sales_items"]:
            for row in buffers[k]:
                stream.append((k, row))
    
    logger.info("✅ Stream construido: %d productos primero, luego %d mensajes más", 
                sizes["products"], len(stream) - sizes["products"])

    # Emitir mensajes
    logger.info(f"Conectando a Kafka en {BROKER} ...")
    logger.info("Empezando a enviar filas…")

    sent, t0 = 0, time.time()
    for k, row in stream:
        topic = TOPICS[k]
        key_field = KEY_FIELDS[k]
        key = str(row.get(key_field, f"key_{sent}"))
        
        try:
            producer.produce(
                topic,
                key=key,
                value=json.dumps(row, ensure_ascii=False),
                callback=delivery_callback
            )
            sent += 1
            
            # Flush periódico para mejor rendimiento
            if sent % 1000 == 0:
                producer.flush(1.0)
                logger.info(f"Enviados {sent} mensajes")
            
            # Control de velocidad
            if EVENTS_PER_SECOND > 0:
                elapsed = time.time() - t0
                expected = sent / EVENTS_PER_SECOND
                if expected > elapsed:
                    time.sleep(min(expected - elapsed, 0.05))
                    
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            continue
    
    # Flush final
    try:
        producer.flush(5.0)
    except Exception as e:
        logger.error(f"Error en flush final: {e}")
    
    logger.info(f"Enviados {sent} eventos totales.")

def main():
    logger = setup_logging()
    logger.info("Iniciando productor ERP ...")
    
    try:
        producer = make_producer()
        if LOOP:
            while True:
                run_once(producer)
        else:
            run_once(producer)
    except Exception as e:
        logger.error(f"Error en el productor: {e}")
        raise
    finally:
        try:
            producer.flush()
            logger.info("Productor cerrado correctamente")
        except Exception as e:
            logger.error(f"Error cerrando productor: {e}")

if __name__ == "__main__":
    random.seed(42)
    main()
