# 🏢 Sistema ERP de Big Data - Arquitectura de Recomendaciones Comerciales

## 📁 Estructura del Proyecto

```
Practica 4/
├── 📊 dashboards/          # Dashboards de visualización (Streamlit)
│   ├── erp_dashboard.py                    # Dashboard estático (datos históricos)
│   ├── erp_dashboard_dinamico.py           # Dashboard dinámico (tiempo real)
│   └── print_recommendations_consumer.py   # Dashboard de recomendaciones ML
│
├── 🔄 services/            # Servicios de mensajería (Kafka/MongoDB)
│   ├── erp_simulator_producer.py   # Productor Kafka (envía datos a Kafka)
│   ├── erp_kafka_to_mongo.py       # Consumidor Kafka → MongoDB
│   └── reco_service_stream.py      # Servicio de recomendaciones en tiempo real
│
├── 🔧 scripts/             # Scripts de una sola ejecución
│   ├── process_superstore_csv.py           # Procesa CSV real → CSV normalizados
│   ├── model_train_reco.py                 # Entrena modelo de ML
│   └── mongo_data_processor_completo.py    # Procesa datos para dashboards estáticos
│
├── ⚙️ config/              # Configuración e infraestructura
│   ├── config.py              # Configuración centralizada (MongoDB, Kafka)
│   ├── docker-compose.yml     # Servicios Docker (Kafka, MongoDB, etc.)
│   └── requirements.txt       # Dependencias Python
│
├── 📚 docs/                # Documentación
│   ├── README.md                              # Documentación principal
│   ├── ARQUITECTURA.md                        # Arquitectura del sistema
│   ├── MIGRACION_DATOS_REALES.md             # Migración a datos reales
│   └── EXPLICACION_MODELO_RECOMENDACIONES.md # Explicación del modelo ML
│
└── 💾 data/                # Datos y modelos
    ├── archive/            # Datos fuente originales
    │   └── Sample - Superstore.csv
    ├── csv_out/            # CSVs procesados (listos para Kafka)
    │   ├── products.csv
    │   ├── customers.csv
    │   ├── sales.csv
    │   └── sales_items.csv
    └── models/             # Modelos entrenados
        └── item_sim.pkl    # Modelo de similitud item-item
```

## 🚀 Inicio Rápido

### 1. Instalar Dependencias
```bash
pip install -r config/requirements.txt
```

### 2. Iniciar Infraestructura
```bash
cd config
docker-compose up -d
```

### 3. Procesar Datos (Una vez)
```bash
python scripts/process_superstore_csv.py
```

### 4. Entrenar Modelo (Una vez)
```bash
python scripts/model_train_reco.py
```

### 5. Ejecutar Pipeline de Datos
```bash
# Terminal 1: Productor Kafka
python services/erp_simulator_producer.py

# Terminal 2: Consumidor Kafka → MongoDB
python services/erp_kafka_to_mongo.py

# Terminal 3: Procesador de datos (opcional, para dashboards estáticos)
python scripts/mongo_data_processor_completo.py

# Terminal 4: Servicio de recomendaciones
python services/reco_service_stream.py
```

### 6. Ejecutar Dashboards
```bash
# Terminal 5: Dashboard Estático (Puerto 8501)
streamlit run dashboards/erp_dashboard.py --server.port 8501

# Terminal 6: Dashboard Dinámico (Puerto 8502)
streamlit run dashboards/erp_dashboard_dinamico.py --server.port 8502

# Terminal 7: Dashboard de Recomendaciones
streamlit run dashboards/print_recommendations_consumer.py
```

## 📖 Documentación Completa

Ver la documentación completa en la carpeta `docs/`:
- `docs/README.md` - Documentación principal del sistema
- `docs/ARQUITECTURA.md` - Arquitectura detallada
- `docs/EXPLICACION_MODELO_RECOMENDACIONES.md` - Explicación del modelo ML

## 🔧 Configuración

Edita `config/config.py` con tus credenciales de MongoDB Atlas.

## 📊 Componentes Principales

### Dashboards (`dashboards/`)
- **erp_dashboard.py**: Análisis histórico de ventas
- **erp_dashboard_dinamico.py**: Monitoreo en tiempo real
- **print_recommendations_consumer.py**: Visualización de recomendaciones ML

### Servicios (`services/`)
- **erp_simulator_producer.py**: Envía datos CSV a Kafka
- **erp_kafka_to_mongo.py**: Consume Kafka y guarda en MongoDB
- **reco_service_stream.py**: Genera recomendaciones en tiempo real

### Scripts (`scripts/`)
- **process_superstore_csv.py**: Procesa datos reales del CSV
- **model_train_reco.py**: Entrena modelo de recomendaciones
- **mongo_data_processor_completo.py**: Crea agregaciones para dashboards

---

**Sistema ERP de Big Data - Arquitectura de Recomendaciones Comerciales** 🏢📊

