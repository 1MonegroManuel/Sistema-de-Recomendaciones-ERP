# 🏢 Sistema ERP de Big Data - Arquitectura de Recomendaciones Comerciales

## 📋 Objetivo

Desarrollar un sistema comercial integral de recomendaciones basado en arquitectura big data que procese datos masivos de un ERP y genere insights comerciales mediante dashboards interactivos.

## 🎯 Objetivos Específicos

### ✅ 1. Fuente de Datos - Sistema ERP
- **Productos**: Catálogo completo con categorías, precios y stock
- **Clientes**: Base de datos de clientes con segmentación
- **Ventas**: Transacciones comerciales con detalles de items

### ✅ 2. Procesador/Productor de Datos
- Procesamiento de datos reales del dataset Superstore (9,994 registros)
- Conversión de formato denormalizado a estructura normalizada (products, customers, sales, sales_items)
- Envío continuo de datos al Data Ingestor

### ✅ 3. Apache Kafka - Data Ingestor
- Procesamiento de streams de datos en tiempo real
- Particionamiento y distribución de mensajes
- Garantía de entrega y orden de mensajes

### ✅ 4. Almacenamiento - MongoDB Atlas
- Data Lake para datos raw (ventas, clientes, productos)
- Data Warehouse con datos procesados y agregados
- Colecciones especializadas para análisis

### ✅ 5. Procesamiento de Datos
- Agregaciones por día, sucursal, producto y cliente
- Análisis estadístico y correlaciones
- Generación de métricas de negocio

### ✅ 6. Motor de Recomendaciones + Visualización
- Entrenamiento del modelo item-based (co-ocurrencia + coseno)
- Servicio en tiempo real que publica recomendaciones enriquecidas
- Dashboards Streamlit (recomendaciones, histórico y dinámico)

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FUENTE DE     │    │   DATA INGESTOR │    │   STORAGE &     │
│   DATOS REALES  │───▶│   APACHE KAFKA  │───▶│   PROCESSING    │
│  (Superstore)   │    │                 │    │   MONGODB ATLAS │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       ▼
         │                       │              ┌─────────────────┐
         │                       │              │   DASHBOARDS    │
         │                       │              │   STREAMLIT     │
         │                       │              │   (Estático +   │
         │                       │              │    Dinámico)    │
         │                       │              └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   GENERADOR     │    │   CONSUMIDOR    │
│   CSV MASIVOS   │    │   KAFKA→MONGO   │
└─────────────────┘    └─────────────────┘
```

## 📦 Componentes del Sistema

### 🔧 Archivos Principales

| Archivo | Función | Descripción |
|---------|---------|-------------|
| `process_superstore_csv.py` | Procesador CSV | Convierte datos reales del CSV Superstore a formato ERP |
| `erp_simulator_producer.py` | Productor Kafka | Envía datos CSV a Kafka (productos primero para asegurar nombres en MongoDB) |
| `erp_kafka_to_mongo.py` | Consumidor Kafka | Recibe datos de Kafka y los guarda en MongoDB |
| `model_train_reco.py` | Entrenamiento ML | Calcula similitud item-item y genera `models/item_sim.pkl` |
| `reco_service_stream.py` | Servicio ML en tiempo real | Consume ventas, calcula recomendaciones y las publica en Kafka/MongoDB |
| `print_recommendations_consumer.py` | Dashboard Recomendaciones | Muestra cada venta, productos comprados y sugerencias con métricas de relevancia |
| `mongo_data_processor_completo.py` | Procesador | Crea agregaciones y análisis de datos |
| `erp_dashboard.py` | Dashboard Estático | Visualización de datos procesados |
| `erp_dashboard_dinamico.py` | Dashboard Dinámico | Monitoreo en tiempo real |
| `config.py` | Configuración | Configuración centralizada del sistema |
| `docker-compose.yml` | Infraestructura | Servicios Docker (Kafka, Kafdrop, etc.) |

### 🗄️ Colecciones MongoDB

#### Datos Raw (Data Lake)
- `sales` - Transacciones de ventas
- `customers` - Base de datos de clientes
- `products` - Catálogo de productos
- `sales_items` - Detalle de items por venta

#### Datos Procesados (Data Warehouse)
- `daily_sales_summary` - Resúmenes diarios de ventas
- `store_analysis` - Análisis por sucursal
- `top_products` - Productos más vendidos
- `customer_analysis` - Análisis de clientes
- `category_analysis` - Análisis por categorías

## 🚀 Instalación y Configuración

### 📋 Prerrequisitos

- **Python 3.8+**
- **Docker y Docker Compose**
- **Git**
- **Conexión a Internet** (para MongoDB Atlas)

### 🔧 Dependencias Python

```bash
pip install pymongo confluent-kafka streamlit pandas plotly scipy seaborn matplotlib numpy kafka-python
```

O instalar desde requirements.txt:
```bash
pip install -r requirements.txt
```

### 🌐 Configuración MongoDB Atlas

1. **Crear cuenta en [MongoDB Atlas](https://cloud.mongodb.com/)**
2. **Crear cluster** (gratuito disponible)
3. **Crear usuario** con permisos de lectura/escritura
4. **Agregar IP a whitelist** (0.0.0.0/0 para desarrollo)
5. **Obtener connection string**

### ⚙️ Configuración del Sistema

1. **Actualizar `config.py`** con tus credenciales:
```python
MONGODB_USERNAME = "tu_usuario"
MONGODB_PASSWORD = "tu_contraseña"
MONGODB_CLUSTER = "tu_cluster.mongodb.net"
```

2. **Verificar puertos disponibles**:
   - Kafka: 9094
   - Kafdrop: 9000
   - Dashboard Estático: 8501
   - Dashboard Dinámico: 8502

## 🏃‍♂️ Ejecución del Sistema

### 1️⃣ Iniciar Infraestructura
```bash
# Iniciar servicios Docker (Kafka, Kafdrop, etc.)
docker-compose up -d

# Verificar que los servicios estén corriendo
docker ps
```

### 2️⃣ Procesar Datos Reales
```bash
# Procesar datos reales del CSV Superstore (9,994 registros)
python process_superstore_csv.py
```

### 3️⃣ Ejecutar Pipeline de Datos
```bash
# Terminal 1: Productor Kafka
python erp_simulator_producer.py

# Terminal 2: Consumidor Kafka → MongoDB
python erp_kafka_to_mongo.py

# Terminal 3: Procesador de Datos
python mongo_data_processor_completo.py
```

### 4️⃣ Ejecutar Dashboards
```bash
# Terminal 4: Dashboard Estático (Puerto 8501)
streamlit run erp_dashboard.py --server.port 8501

# Terminal 5: Dashboard Dinámico (Puerto 8502)
streamlit run erp_dashboard_dinamico.py --server.port 8502
```

## 📊 Dashboards

### 🎯 Dashboard de Recomendaciones (Streamlit)
- **Archivo**: `print_recommendations_consumer.py`
- **Entrada**: tópico Kafka `erp.recommendations` o colección `recommendations` en MongoDB (respaldo)
- **Qué muestra**:
  - Información completa de la venta (cliente, tienda, pago, fecha, totales)
  - Productos comprados con nombres, categorías, cantidades, precios y subtotal
  - Productos recomendados con métricas de ML en porcentaje (relevancia, confianza, ranking)
  - Gráficos de barras e histogramas de relevancia, más métricas agregadas
- **Extras**: botón de actualización manual, auto-refresh cada 10 segundos, lectura de MongoDB cuando Kafka está vacío

### 📈 Dashboard Estático (Puerto 8501)
- **Análisis histórico** de ventas
- **Filtros por año/mes**
- **Métricas agregadas** por sucursal
- **Exportación** a Excel/CSV
- **Gráficos estadísticos**

### ⚡ Dashboard Dinámico (Puerto 8502)
- **Monitoreo en tiempo real**
- **Filtros por fecha**
- **Ventas por hora** (coloreadas por sucursal)
- **Auto-refresh** cada 5 segundos
- **Datos actualizados** constantemente

## 🔍 Monitoreo y Debugging

### 📊 Kafdrop (Puerto 9000)
- **Monitoreo de Kafka** en tiempo real
- **Visualización de tópicos** y mensajes
- **Métricas de rendimiento**

### 🐳 Docker Logs
```bash
# Ver logs de Kafka
docker logs kafka

# Ver logs de MongoDB
docker logs mongo
```

### 📝 Logs de Aplicación
- **Productor**: Logs de envío de mensajes
- **Consumidor**: Logs de recepción y guardado
- **Procesador**: Logs de agregaciones
- **Dashboards**: Logs de conexión a MongoDB

## 📈 Métricas del Sistema

### 📊 Volumen de Datos (Datos Reales - Superstore)
- **Productos**: 1,862 productos únicos (con nombres, categorías y `unit_price` preservados en MongoDB)
- **Clientes**: 793 clientes únicos (nombres y correos generados para completar el dataset)
- **Ventas**: 5,009 órdenes
- **Items de Venta**: 9,994 líneas de venta
- **Recomendaciones ML**: hasta 5 sugerencias por venta con relevancia calculada por el modelo item-based

### ⚡ Rendimiento
- **Productor Kafka**: 20 mensajes/segundo
- **Consumidor**: Procesamiento en lotes de 1,000
- **Procesador**: Agregaciones optimizadas
- **Dashboards**: Cache de 5 segundos (dinámico)

## 🛠️ Solución de Problemas

### ❌ Error de Conexión a MongoDB
```bash
# Verificar credenciales en config.py
# Verificar whitelist de IP en MongoDB Atlas
# Verificar que el cluster esté activo
```

### ❌ Error de Conexión a Kafka
```bash
# Verificar que Docker esté corriendo
docker-compose up -d

# Verificar puerto 9094
netstat -an | findstr 9094
```

### ❌ Error de Dependencias
```bash
# Reinstalar dependencias
pip install --upgrade -r requirements.txt
```

## 📚 Estructura de Archivos

```
Practica 4/
├── 📁 archive/                    # Dataset real (Sample - Superstore.csv)
├── 📁 csv_out/                    # Datos normalizados listos para Kafka
├── 📁 models/                     # Modelo de similitud (`item_sim.pkl`)
├── 🧠 model_train_reco.py         # Entrenamiento del modelo de recomendaciones
├── ⚙️ reco_service_stream.py      # Servicio en tiempo real (Kafka → ML → MongoDB)
├── 🎯 print_recommendations_consumer.py  # Dashboard de recomendaciones
├── 🔧 erp_simulator_producer.py   # Productor Kafka
├── 🔧 erp_kafka_to_mongo.py       # Consumidor Kafka → MongoDB
├── 🔧 mongo_data_processor_completo.py  # Procesamiento de agregados
├── 📊 erp_dashboard.py            # Dashboard estático
├── ⚡ erp_dashboard_dinamico.py    # Dashboard dinámico
├── ⚙️ config.py                   # Configuración centralizada
├── 🐳 docker-compose.yml          # Servicios Docker
└── 📖 README.md                   # Esta documentación
```

## 🎯 Casos de Uso

### 📊 Análisis Comercial
- **Tendencias de ventas** por período
- **Rendimiento por sucursal**
- **Productos más vendidos**
- **Análisis de clientes**

### 🔍 Monitoreo Operativo
- **Ventas en tiempo real**
- **Alertas de rendimiento**
- **Métricas de negocio**

### 📈 Reportes Ejecutivos
- **Dashboards interactivos**
- **Exportación de datos**
- **Visualizaciones avanzadas**

## 🚀 Próximos Pasos

1. **Escalabilidad**: Implementar más nodos de Kafka
2. **Machine Learning**: Agregar algoritmos de recomendación
3. **Alertas**: Sistema de notificaciones en tiempo real
4. **API REST**: Exponer datos mediante API
5. **Microservicios**: Separar componentes en servicios independientes

---

## 👥 Autores

**Manuel Monegro** - Universidad - Tecnologías Emergentes I

## 📄 Licencia

Este proyecto es parte de un trabajo académico para la materia de Tecnologías Emergentes I.

---

*Sistema ERP de Big Data - Arquitectura de Recomendaciones Comerciales* 🏢📊
