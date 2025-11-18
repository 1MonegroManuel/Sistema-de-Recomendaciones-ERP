# mongo_data_processor_completo.py
# Procesador completo de datos ERP para crear resúmenes y análisis
import pymongo
from pymongo import MongoClient
import pandas as pd
from datetime import datetime, timedelta
import logging
from config import MONGODB_CONNECTION_STRING, MONGODB_DATABASE, COLLECTIONS

# ---------- Configuración ----------
MONGO_URI = MONGODB_CONNECTION_STRING
DB_NAME = MONGODB_DATABASE

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def create_daily_sales_summary(db, logger):
    """Crea resumen diario de ventas"""
    logger.info("Creando resumen diario de ventas...")
    
    pipeline = [
        {
            "$addFields": {
                "sale_date": {
                    "$dateFromString": {
                        "dateString": "$sale_datetime",
                        "format": "%Y-%m-%d %H:%M:%S"
                    }
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$sale_date"},
                    "month": {"$month": "$sale_date"},
                    "day": {"$dayOfMonth": "$sale_date"}
                },
                "total_sales": {"$sum": "$total_amount"},
                "total_orders": {"$sum": 1},
                "avg_order_value": {"$avg": "$total_amount"},
                "total_customers": {"$addToSet": "$customer_id"},
                "total_items": {"$sum": "$items_count"}
            }
        },
        {
            "$project": {
                "date": {
                    "$dateFromParts": {
                        "year": "$_id.year",
                        "month": "$_id.month",
                        "day": "$_id.day"
                    }
                },
                "total_sales": 1,
                "total_orders": 1,
                "avg_order_value": 1,
                "total_customers": {"$size": "$total_customers"},
                "total_items": 1
            }
        },
        {"$sort": {"date": 1}}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    
    if result:
        # Limpiar colección existente
        db.daily_sales_summary.delete_many({})
        
        # Insertar nuevos datos
        db.daily_sales_summary.insert_many(result)
        logger.info(f"Resumen diario creado: {len(result)} días procesados")
        
        # Mostrar estadísticas
        total_sales = sum(day['total_sales'] for day in result)
        total_orders = sum(day['total_orders'] for day in result)
        logger.info(f"  - Total ventas: ${total_sales:,.2f}")
        logger.info(f"  - Total órdenes: {total_orders:,}")
    else:
        logger.warning("No se encontraron datos de ventas para procesar")

def create_store_analysis(db, logger):
    """Crea análisis de tiendas"""
    logger.info("Creando análisis de tiendas...")
    
    pipeline = [
        {
            "$group": {
                "_id": "$store_id",
                "total_sales": {"$sum": "$total_amount"},
                "total_orders": {"$sum": 1},
                "avg_order_value": {"$avg": "$total_amount"},
                "total_items": {"$sum": "$items_count"},
                "unique_customers": {"$addToSet": "$customer_id"}
            }
        },
        {
            "$project": {
                "store_id": "$_id",
                "total_sales": 1,
                "total_orders": 1,
                "avg_order_value": 1,
                "total_items": 1,
                "unique_customers": {"$size": "$unique_customers"}
            }
        },
        {"$sort": {"total_sales": -1}}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    
    if result:
        # Limpiar colección existente
        db.store_analysis.delete_many({})
        
        # Insertar nuevos datos
        db.store_analysis.insert_many(result)
        logger.info(f"Análisis de tiendas creado: {len(result)} tiendas procesadas")
        
        # Mostrar estadísticas
        for store in result:
            logger.info(f"  - Tienda {store['store_id']}: ${store['total_sales']:,.2f} en {store['total_orders']} órdenes")
    else:
        logger.warning("No se encontraron datos de tiendas para procesar")

def create_top_products(db, logger):
    """Crea ranking de productos más vendidos"""
    logger.info("Creando ranking de productos...")
    
    # Primero necesitamos unir sales con sales_items
    pipeline = [
        {
            "$lookup": {
                "from": "sales_items",
                "localField": "sale_id",
                "foreignField": "sale_id",
                "as": "items"
            }
        },
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "total_quantity": {"$sum": "$items.quantity"},
                "total_revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.unit_price"]}},
                "total_orders": {"$addToSet": "$sale_id"}
            }
        },
        {
            "$project": {
                "product_id": "$_id",
                "total_quantity": 1,
                "total_revenue": 1,
                "total_orders": {"$size": "$total_orders"}
            }
        },
        {"$sort": {"total_revenue": -1}},
        {"$limit": 50}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    
    if result:
        # Limpiar colección existente
        db.top_products.delete_many({})
        
        # Insertar nuevos datos
        db.top_products.insert_many(result)
        logger.info(f"Ranking de productos creado: {len(result)} productos")
        
        # Mostrar top 5
        for i, product in enumerate(result[:5]):
            logger.info(f"  {i+1}. Producto {product['product_id']}: ${product['total_revenue']:,.2f}")
    else:
        logger.warning("No se encontraron datos de productos para procesar")

def create_customer_analysis(db, logger):
    """Crea análisis de clientes"""
    logger.info("Creando análisis de clientes...")
    
    pipeline = [
        {
            "$addFields": {
                "sale_date": {
                    "$dateFromString": {
                        "dateString": "$sale_datetime",
                        "format": "%Y-%m-%d %H:%M:%S"
                    }
                }
            }
        },
        {
            "$group": {
                "_id": "$customer_id",
                "total_spent": {"$sum": "$total_amount"},
                "total_orders": {"$sum": 1},
                "avg_order_value": {"$avg": "$total_amount"},
                "first_purchase": {"$min": "$sale_date"},
                "last_purchase": {"$max": "$sale_date"},
                "stores_visited": {"$addToSet": "$store_id"}
            }
        },
        {
            "$project": {
                "customer_id": "$_id",
                "total_spent": 1,
                "total_orders": 1,
                "avg_order_value": 1,
                "first_purchase": 1,
                "last_purchase": 1,
                "stores_visited": {"$size": "$stores_visited"}
            }
        },
        {"$sort": {"total_spent": -1}},
        {"$limit": 100}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    
    if result:
        # Limpiar colección existente
        db.customer_analysis.delete_many({})
        
        # Insertar nuevos datos
        db.customer_analysis.insert_many(result)
        logger.info(f"Análisis de clientes creado: {len(result)} clientes")
        
        # Mostrar top 5
        for i, customer in enumerate(result[:5]):
            logger.info(f"  {i+1}. Cliente {customer['customer_id']}: ${customer['total_spent']:,.2f}")
    else:
        logger.warning("No se encontraron datos de clientes para procesar")

def create_category_analysis(db, logger):
    """Crea análisis por categorías"""
    logger.info("Creando análisis por categorías...")
    
    # Unir sales_items con products para obtener categorías
    pipeline = [
        {
            "$lookup": {
                "from": "sales_items",
                "localField": "sale_id",
                "foreignField": "sale_id",
                "as": "items"
            }
        },
        {"$unwind": "$items"},
        {
            "$lookup": {
                "from": "products",
                "localField": "items.product_id",
                "foreignField": "product_id",
                "as": "product"
            }
        },
        {"$unwind": "$product"},
        {
            "$group": {
                "_id": {
                    "category": "$product.category",
                    "subcategory": "$product.subcategory"
                },
                "total_revenue": {"$sum": {"$multiply": ["$items.quantity", "$items.unit_price"]}},
                "total_quantity": {"$sum": "$items.quantity"},
                "total_orders": {"$addToSet": "$sale_id"}
            }
        },
        {
            "$project": {
                "category": "$_id.category",
                "subcategory": "$_id.subcategory",
                "total_revenue": 1,
                "total_quantity": 1,
                "total_orders": {"$size": "$total_orders"}
            }
        },
        {"$sort": {"total_revenue": -1}}
    ]
    
    result = list(db.sales.aggregate(pipeline))
    
    if result:
        # Limpiar colección existente
        db.category_analysis.delete_many({})
        
        # Insertar nuevos datos
        db.category_analysis.insert_many(result)
        logger.info(f"Análisis de categorías creado: {len(result)} categorías")
        
        # Mostrar top 5
        for i, category in enumerate(result[:5]):
            logger.info(f"  {i+1}. {category['category']} - {category['subcategory']}: ${category['total_revenue']:,.2f}")
    else:
        logger.warning("No se encontraron datos de categorías para procesar")

def main():
    logger = setup_logging()
    logger.info("Iniciando procesamiento completo de datos ERP...")
    
    try:
        # Conectar a MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        
        # Verificar conexión
        client.admin.command('ping')
        logger.info("Conectado a MongoDB exitosamente")
        
        # Verificar colecciones existentes
        collections = db.list_collection_names()
        logger.info(f"Colecciones disponibles: {collections}")
        
        # Verificar que existan las colecciones necesarias
        required_collections = ['sales']
        missing_collections = [col for col in required_collections if col not in collections]
        
        if missing_collections:
            logger.error(f"Colecciones faltantes: {missing_collections}")
            logger.error("Ejecuta primero el productor y consumidor de Kafka")
            return
        
        # Contar documentos en sales
        sales_count = db.sales.count_documents({})
        logger.info(f"Documentos en sales: {sales_count:,}")
        
        if sales_count == 0:
            logger.warning("No hay datos de ventas para procesar")
            return
        
        # Crear todos los análisis
        create_daily_sales_summary(db, logger)
        create_store_analysis(db, logger)
        create_top_products(db, logger)
        create_customer_analysis(db, logger)
        create_category_analysis(db, logger)
        
        logger.info("Procesamiento completado exitosamente")
        
        # Mostrar resumen final
        logger.info("=== RESUMEN FINAL ===")
        for collection in ['daily_sales_summary', 'store_analysis', 'top_products', 'customer_analysis', 'category_analysis']:
            count = db[collection].count_documents({})
            logger.info(f"{collection}: {count} documentos")
        
    except Exception as e:
        logger.error(f"Error en el procesamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
