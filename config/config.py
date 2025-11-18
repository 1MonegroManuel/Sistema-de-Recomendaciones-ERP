# config.py
# Configuración centralizada para MongoDB Atlas

# MongoDB Atlas Configuration
MONGODB_USERNAME = "yjxk46N6fPrMUYUW"
MONGODB_PASSWORD = "0u5TvopxVv7p9ryV"  # Reemplaza con tu contraseña real
MONGODB_CLUSTER = "tecnologiasemergentes.3x39pfq.mongodb.net"
MONGODB_DATABASE = "erp_database"

# Connection String
MONGODB_CONNECTION_STRING = f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_CLUSTER}/{MONGODB_DATABASE}?retryWrites=true&w=majority&appName=TecnologiasEmergentes"

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = "localhost:9094"
KAFKA_TOPIC = "erp_sales"

# Collections
COLLECTIONS = {
    "SALES": "sales",
    "CUSTOMERS": "customers", 
    "PRODUCTS": "products",
    "SALES_ITEMS": "sales_items",
    "DAILY_SALES_SUMMARY": "daily_sales_summary",
    "STORE_ANALYSIS": "store_analysis",
    "TOP_PRODUCTS": "top_products",
    "CUSTOMER_ANALYSIS": "customer_analysis",
    "CATEGORY_ANALYSIS": "category_analysis"
}
