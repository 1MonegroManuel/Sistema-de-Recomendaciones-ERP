# 🏗️ Arquitectura del Sistema de Recomendaciones ERP

## 📊 Visión General

```
┌──────────────────────────────────────────────────────────┐
│                   FLUJO PRINCIPAL (Resumen)              │
├──────────────────────────────────────────────────────────┤
│ Fuente CSV ─▶ Productor Kafka ─▶ MongoDB ─▶ ML ─▶ Dashboards │
└──────────────────────────────────────────────────────────┘
```

Esta arquitectura prioriza el pipeline de recomendaciones en tiempo real. Todo gira alrededor de ocho componentes clave que se mantienen sincronizados mediante Kafka, MongoDB y Streamlit.

## 🔑 Componentes Esenciales

- `docker-compose.yml`: levanta Kafka, Kafdrop y MongoDB para todo el ecosistema.
- `erp_simulator_producer.py`: carga los CSV normalizados y envía los mensajes al clúster de Kafka en el orden correcto (productos primero, después clientes, ventas y líneas).
- `erp_kafka_to_mongo.py`: consume los tópicos `erp.*` y hace upsert en las colecciones de MongoDB (`products`, `customers`, `sales`, `sales_items`).
- `model_train_reco.py`: entrena el modelo item-based (co-ocurrencia + coseno) y genera `models/item_sim.pkl` con las relevancias entre productos.
- `reco_service_stream.py`: escucha ventas desde `erp.sales`, recolecta la cesta en MongoDB, calcula recomendaciones con el modelo, enriquece con nombres/porcentajes y publica la carga en Kafka y MongoDB (`recommendations`).
- `print_recommendations_consumer.py`: dashboard Streamlit que consume el tópico `erp.recommendations` (o MongoDB de respaldo) y muestra cada venta con sus compras y recomendaciones enriquecidas.
- `mongo_data_processor_completo.py`: genera resúmenes agregados (ventas diarias, ranking por tienda, top productos, clientes, categorías) para los dashboards históricos.
- `erp_dashboard.py` y `erp_dashboard_dinamico.py`: dashboards Streamlit para visualización histórica y monitoreo en tiempo real respectivamente.

## 🔄 Flujo de Datos Detallado

```
CSV (csv_out/*.csv)
    │
    ▼
erp_simulator_producer.py ──► Kafka tópicos erp.* ──► erp_kafka_to_mongo.py ──► MongoDB Atlas
                                                                              │
                                                                              ├─► model_train_reco.py (entrenamiento offline)
                                                                              │       └─► models/item_sim.pkl
                                                                              │
                                                                              └─► reco_service_stream.py (online)
                                                                                      ├─► Kafka erp.recommendations
                                                                                      └─► MongoDB recommendations

Kafka / MongoDB ──► print_recommendations_consumer.py (dashboard en vivo)
MongoDB           ──► mongo_data_processor_completo.py ──► colecciones agregadas ──► erp_dashboard*.py
```

## ⚙️ Roles de los Servicios

- **Kafka (`docker-compose.yml`)**: maneja el streaming de eventos `erp.products`, `erp.customers`, `erp.sales`, `erp.sales_items` y `erp.recommendations` sobre `localhost:9094`.
- **MongoDB Atlas**: almacén central de datos crudos y enriquecidos; permite consultas rápidas para dashboards y para el servicio de recomendaciones.
- **Streamlit** (`print_recommendations_consumer.py`, `erp_dashboard.py`, `erp_dashboard_dinamico.py`): capa de presentación para usuarios finales (puertos 8501 y 8502).

## 🧠 Motor de Recomendaciones

1. `model_train_reco.py` calcula la similitud item-item ponderada por recencia y genera un diccionario de relevancias.
2. `reco_service_stream.py` combina el modelo con las cestas reales:
   - Recupera `sales_items` desde MongoDB.
   - Obtiene las mejores coincidencias (`relevancia`) del modelo.
   - Enriquecer con nombres, categorías y porcentajes (relevancia, confianza, ranking).
   - Guarda y publica el resultado para consumo inmediato.

## 🖥️ Dashboards

- `print_recommendations_consumer.py`: vista detallada por venta (cliente, tienda, método de pago, productos comprados, recomendaciones y métricas de ML).
- `erp_dashboard.py`: análisis histórico generado a partir de las colecciones agregadas (`daily_sales_summary`, `store_analysis`, etc.).
- `erp_dashboard_dinamico.py`: monitoreo en vivo de ventas utilizando consultas directas a `sales` y filtros en tiempo real.

## 🔧 Operación Básica

1. Levantar infraestructura: `docker-compose up -d` (Kafka, MongoDB, Kafdrop, etc.).
2. Procesar CSV reales si es necesario y ejecutar `erp_simulator_producer.py` para poblar Kafka.
3. Ejecutar `erp_kafka_to_mongo.py` para persistir en MongoDB.
4. Entrenar el modelo con `model_train_reco.py` (cuando se ingrese nuevo histórico significativo).
5. Iniciar `reco_service_stream.py` para generar recomendaciones en tiempo real.
6. Abrir dashboards Streamlit según necesidad:
   - `print_recommendations_consumer.py` (tiempo real con recomendaciones).
   - `erp_dashboard.py` / `erp_dashboard_dinamico.py` (histórico y live business).
7. Ejecutar `mongo_data_processor_completo.py` periódicamente para refrescar agregados.

## 🌐 Puertos y Conexiones

- Kafka (broker externo): `127.0.0.1:9094`
- Kafdrop (verificación tópicos): `http://localhost:9000`
- MongoDB (Docker local o Atlas): `mongodb://admin:admin123@localhost:27017` (o string Atlas de `config.py`)
- Dashboards Streamlit: `http://localhost:8501` y `http://localhost:8502`

---

Arquitectura enfocada en recomendaciones en tiempo real, mantenida únicamente con los módulos críticos del proyecto.
